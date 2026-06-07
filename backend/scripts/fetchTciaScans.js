const axios = require("axios");
const AdmZip = require("adm-zip");
const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const BASE_URL = "https://services.cancerimagingarchive.net/nbia-api/services/v1";
const LIMIT = Math.min(Math.max(Number(process.env.TCIA_SCAN_LIMIT || 5), 1), 5);
const MAX_BYTES = Number(process.env.TCIA_MAX_SERIES_BYTES || 80 * 1024 * 1024);
const ROOT = path.resolve(__dirname, "..");
const DOWNLOADS = path.join(ROOT, "downloads");
const SCANS_FILE = path.join(ROOT, "scans.json");
const PNG_DIR = path.join(ROOT, "media", "scans");
const PYTHON = process.env.PYTHON || path.join(ROOT, "venv", "Scripts", "python.exe");
const GENERATED_SCAN_PATTERN = /\.(png|jpe?g)$/i;
const EXCLUDED_SERIES = /seg|report|derived|localizer|scout|calib|reference|survey|screen save|dose/i;
const PROFILES = [
  {
    collection: "LIDC-IDRI",
    modality: "CT",
    bodyPart: "CHEST",
    minImages: 50,
    preferred: /chest|lung|cap|thorax/i,
    displayBodyPart: "Chest / lungs",
    clinicalContext: "LIDC-IDRI is a public thoracic CT collection created for lung-nodule research.",
    focusHint: "Review visible lung fields for nodules, masses, consolidation, pleural abnormality, and other thoracic findings.",
    department: "Thoracic Radiology / Pulmonology",
  },
  {
    collection: "TCGA-BRCA",
    modality: "MR",
    bodyPart: "BREAST",
    minImages: 30,
    preferred: /vibrant|dynamic|post|pre|sag|ax|breast/i,
    displayBodyPart: "Breast",
    clinicalContext: "TCGA-BRCA contains breast cancer imaging associated with The Cancer Genome Atlas.",
    focusHint: "Review visible breast tissue for mass-like enhancement, asymmetry, architectural distortion, and other suspicious features.",
    department: "Breast Imaging / Oncology",
  },
  {
    collection: "TCGA-KIRC",
    modality: "CT",
    bodyPart: "KIDNEY",
    minImages: 10,
    preferred: /renal|kidney|nephro|abd/i,
    displayBodyPart: "Kidneys",
    clinicalContext: "TCGA-KIRC contains kidney renal clear cell carcinoma imaging associated with The Cancer Genome Atlas.",
    focusHint: "Review visible kidneys for focal masses, contour abnormalities, collecting-system changes, and extension beyond the kidney.",
    department: "Abdominal Radiology / Urology",
  },
  {
    collection: "TCGA-LIHC",
    modality: "CT",
    bodyPart: "LIVER",
    minImages: 30,
    preferred: /liver|hepatic|arterial|portal|venous|abd|body/i,
    displayBodyPart: "Liver",
    clinicalContext: "TCGA-LIHC contains liver hepatocellular carcinoma imaging associated with The Cancer Genome Atlas.",
    focusHint: "Review visible liver tissue for focal lesions, contour changes, biliary dilation, and other abdominal abnormalities.",
    department: "Abdominal Radiology / Hepatology",
  },
  {
    collection: "PROSTATEx",
    modality: "MR",
    bodyPart: "PROSTATE",
    minImages: 20,
    preferred: /t2|adc|dwi|prostate/i,
    displayBodyPart: "Prostate",
    clinicalContext: "PROSTATEx is a public prostate MRI collection created for clinically significant cancer detection research.",
    focusHint: "Review visible prostate tissue for focal signal abnormalities, contour changes, and extension beyond the gland.",
    department: "Genitourinary Radiology / Urology",
  },
];

const safeName = value => String(value || "").replace(/[^\w.-]+/g, "_").slice(0, 80);
const bytes = value => Number(String(value || "0").replace(/[^\d.]/g, "")) || 0;

async function get(endpoint, params) {
  const response = await axios.get(`${BASE_URL}/${endpoint}`, { params, timeout: 120000 });
  return response.data;
}

async function downloadSeries(series, profile, index) {
  const id = `tcia_scan_${String(index + 1).padStart(3, "0")}`;
  const folder = path.join(DOWNLOADS, `${id}_${safeName(series.PatientID)}`);
  const archive = `${folder}.zip`;
  fs.mkdirSync(folder, { recursive: true });
  console.log(`Downloading ${id}: ${series.SeriesDescription || series.ProtocolName || series.SeriesInstanceUID}`);
  const response = await axios.get(`${BASE_URL}/getImage`, {
    params: { SeriesInstanceUID: series.SeriesInstanceUID },
    responseType: "arraybuffer",
    timeout: 300000,
    maxContentLength: MAX_BYTES,
    maxBodyLength: MAX_BYTES,
  });
  fs.writeFileSync(archive, response.data);
  new AdmZip(archive).extractAllTo(folder, true);
  const imageFile = `${id}.png`;
  execFileSync(PYTHON, [path.join(__dirname, "dicom_to_png.py"), folder, path.join(PNG_DIR, imageFile)], { stdio: "inherit" });
  return {
    id,
    patientId: series.PatientID || `tcia_patient_${index + 1}`,
    title: `${profile.displayBodyPart} ${series.Modality} - ${series.Collection}`,
    imageFile,
    modality: series.Modality,
    bodyPart: profile.displayBodyPart,
    symptoms: [],
    symptomsSource: "Not provided by TCIA/NBIA",
    userComplaint: "No patient-reported complaint is available from the TCIA/NBIA imaging API for this de-identified case.",
    clinicalContext: profile.clinicalContext,
    focusHint: profile.focusHint,
    source: "TCIA/NBIA",
    sourceUrl: series.CollectionURI || "https://www.cancerimagingarchive.net/",
    collection: series.Collection,
    licenseName: series.LicenseName || "",
    licenseURI: series.LicenseURI || "",
    studyInstanceUID: series.StudyInstanceUID,
    seriesInstanceUID: series.SeriesInstanceUID,
    seriesDescription: series.SeriesDescription || "",
    imageCount: Number(series.ImageCount || 0),
    recommendedDepartment: profile.department,
  };
}

async function main() {
  fs.mkdirSync(DOWNLOADS, { recursive: true });
  fs.mkdirSync(PNG_DIR, { recursive: true });
  const scans = [];
  for (const [index, profile] of PROFILES.slice(0, LIMIT).entries()) {
    try {
      const series = await get("getSeries", { Collection: profile.collection, Modality: profile.modality });
      const selected = series
        .filter(item => String(item.BodyPartExamined || "").toUpperCase().includes(profile.bodyPart))
        .filter(item => Number(item.ImageCount || 0) >= profile.minImages)
        .filter(item => !bytes(item.FileSize) || bytes(item.FileSize) <= MAX_BYTES)
        .filter(item => !EXCLUDED_SERIES.test(`${item.SeriesDescription || ""} ${item.ProtocolName || ""}`))
        .filter(item => profile.preferred.test(`${item.SeriesDescription || ""} ${item.ProtocolName || ""}`))
        .sort((a, b) => (bytes(b.FileSize) / Number(b.ImageCount || 1)) - (bytes(a.FileSize) / Number(a.ImageCount || 1)))[0];
      if (!selected) throw new Error(`No suitable series found in ${profile.collection}.`);
      scans.push(await downloadSeries(selected, profile, index));
    } catch (error) {
      console.warn(`Skipped ${profile.collection}: ${error.message}`);
    }
  }
  if (!scans.length) throw new Error("No TCIA series could be downloaded and converted. Existing scans.json was preserved.");
  const activeImages = new Set(scans.map(scan => scan.imageFile));
  for (const imageFile of fs.readdirSync(PNG_DIR)) {
    if (GENERATED_SCAN_PATTERN.test(imageFile) && !activeImages.has(imageFile)) {
      fs.rmSync(path.join(PNG_DIR, imageFile));
    }
  }
  fs.writeFileSync(SCANS_FILE, `${JSON.stringify(scans, null, 2)}\n`);
  console.log(`Saved ${scans.length} real TCIA scan cases. Removed non-TCIA placeholder cases and stale images.`);
}

main().catch(error => {
  console.error(`TCIA fetch failed: ${error.message}`);
  process.exitCode = 1;
});
