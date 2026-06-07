"use client";

import { useRouter } from "next/navigation";
import {
  useEffect,
  useState,
  type FormEvent,
  type HTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";

import { useAuth } from "@/components/auth-provider";
import {
  ApiError,
  fetchDoctorPatientWorkspace,
  submitDoctorPatientWorkspace,
  type DoctorPatientAssignment,
  type DoctorPatientWorkspace,
  type LaboratoryResultSummary,
} from "@/lib/auth-client";

type FieldErrors = Record<string, string[]>;

function fieldError(errors: FieldErrors, ...keys: string[]) {
  for (const key of keys) {
    const first = errors[key]?.[0];
    if (first) {
      return first;
    }
  }

  return null;
}

function inputClassName(hasError: boolean) {
  return `field-input ${hasError ? "border-rose-300 shadow-[0_0_0_4px_rgba(244,63,94,0.08)]" : ""}`;
}

const defaultSubmissionState = {
  laboratoryRequest: "",
  laboratoryName: "",
  collectedAt: "",
  reportedAt: "",
  diagnosisKind: "blood_test",
  title: "",
  happenedAt: "",
  rawText: "",
  testResults: `[
  {
    "test_name": "CRP",
    "value": 18,
    "unit": "mg/L",
    "flag": "HIGH"
  }
]`,
  rawJson: "{}",
};

export function DoctorPatientsManager() {
  const router = useRouter();
  const {
    assignPatientToDoctor,
    fetchAssignedPatients,
    isAuthenticated,
    isLoading,
    user,
  } = useAuth();
  const [assignments, setAssignments] = useState<DoctorPatientAssignment[]>([]);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<number | null>(
    null,
  );
  const [workspace, setWorkspace] = useState<DoctorPatientWorkspace | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [submissionSuccess, setSubmissionSuccess] = useState<string | null>(null);
  const [isSubmittingAssignment, setIsSubmittingAssignment] = useState(false);
  const [isSubmittingWorkspace, setIsSubmittingWorkspace] = useState(false);
  const [isFetchingAssignments, setIsFetchingAssignments] = useState(true);
  const [isFetchingWorkspace, setIsFetchingWorkspace] = useState(false);
  const [submissionState, setSubmissionState] = useState(defaultSubmissionState);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login?next=/doctor/patients");
      return;
    }

    if (!isLoading && user && user.role !== "doctor") {
      router.replace("/account");
    }
  }, [isAuthenticated, isLoading, router, user]);

  useEffect(() => {
    if (!user || user.role !== "doctor") {
      return;
    }

    let isCancelled = false;

    async function loadAssignments() {
      setIsFetchingAssignments(true);
      setFormError(null);

      try {
        const nextAssignments = await fetchAssignedPatients();
        if (!isCancelled) {
          setAssignments(nextAssignments);
          setSelectedAssignmentId((current) => {
            if (current && nextAssignments.some((item) => item.id === current)) {
              return current;
            }

            return nextAssignments[0]?.id ?? null;
          });
        }
      } catch (error) {
        if (!isCancelled) {
          setFormError(
            error instanceof Error
              ? error.message
              : "We could not load the assigned patients right now.",
          );
        }
      } finally {
        if (!isCancelled) {
          setIsFetchingAssignments(false);
        }
      }
    }

    void loadAssignments();

    return () => {
      isCancelled = true;
    };
  }, [fetchAssignedPatients, user]);

  useEffect(() => {
    if (!selectedAssignmentId || !user || user.role !== "doctor") {
      setWorkspace(null);
      return;
    }

    let isCancelled = false;
    const assignmentId = selectedAssignmentId;

    async function loadWorkspace() {
      setIsFetchingWorkspace(true);
      setWorkspaceError(null);

      try {
        const nextWorkspace = await fetchDoctorPatientWorkspace(assignmentId);
        if (!isCancelled) {
          setWorkspace(nextWorkspace);
        }
      } catch (error) {
        if (!isCancelled) {
          setWorkspaceError(
            error instanceof Error
              ? error.message
              : "We could not load the selected patient workspace.",
          );
        }
      } finally {
        if (!isCancelled) {
          setIsFetchingWorkspace(false);
        }
      }
    }

    void loadWorkspace();

    return () => {
      isCancelled = true;
    };
  }, [selectedAssignmentId, user]);

  async function handleAssignPatient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setFieldErrors({});
    setIsSubmittingAssignment(true);

    const formData = new FormData(event.currentTarget);

    try {
      const response = await assignPatientToDoctor({
        egn: String(formData.get("egn") ?? ""),
        firstName: String(formData.get("firstName") ?? ""),
        middleName: String(formData.get("middleName") ?? ""),
        lastName: String(formData.get("lastName") ?? ""),
      });

      setAssignments((current) => {
        const filtered = current.filter((item) => item.id !== response.assignment.id);
        return [response.assignment, ...filtered];
      });
      setSelectedAssignmentId(response.assignment.id);
      event.currentTarget.reset();
    } catch (error) {
      if (error instanceof ApiError) {
        setFieldErrors(error.fieldErrors);
        setFormError(error.message);
      } else {
        setFormError("We ran into a network issue. Please try again.");
      }
    } finally {
      setIsSubmittingAssignment(false);
    }
  }

  async function handleWorkspaceSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedAssignmentId) {
      setSubmissionError("Select a patient before submitting lab data.");
      return;
    }

    setSubmissionError(null);
    setSubmissionSuccess(null);
    setIsSubmittingWorkspace(true);

    try {
      const response = await submitDoctorPatientWorkspace({
        assignmentId: selectedAssignmentId,
        laboratoryRequest: submissionState.laboratoryRequest,
        laboratoryName: submissionState.laboratoryName,
        collectedAt: submissionState.collectedAt,
        reportedAt: submissionState.reportedAt,
        diagnosisKind: submissionState.diagnosisKind,
        title: submissionState.title,
        happenedAt: submissionState.happenedAt || undefined,
        rawText: submissionState.rawText,
        rawJson: submissionState.rawJson,
        testResults: submissionState.testResults,
        attachments: selectedFiles,
      });

      setWorkspace((current) =>
        current
          ? {
              ...current,
              patient_dashboard: response.patient_dashboard,
              medical_workspace: response.medical_workspace,
            }
          : null,
      );
      setSubmissionSuccess(
        `Submitted ${response.laboratory_result.summary} The analyzer stored a new ${response.diagnosis.kind.replaceAll("_", " ")} diagnosis.`,
      );
      setSelectedFiles([]);
      setSubmissionState((current) => ({
        ...current,
        rawText: "",
        rawJson: "{}",
      }));
    } catch (error) {
      setSubmissionError(
        error instanceof Error
          ? error.message
          : "We could not submit the patient data right now.",
      );
    } finally {
      setIsSubmittingWorkspace(false);
    }
  }

  if (isLoading || !user || user.role !== "doctor") {
    return (
      <main className="mx-auto flex w-full max-w-7xl flex-1 px-5 py-12 sm:px-8">
        <section className="glass-panel w-full animate-pulse p-10">
          <div className="h-5 w-28 rounded-full bg-teal-100" />
          <div className="mt-6 h-16 w-2/3 rounded-3xl bg-slate-200" />
          <div className="mt-10 h-64 rounded-[28px] bg-white/70" />
        </section>
      </main>
    );
  }

  const selectedPatient = workspace?.patient_dashboard.patient;
  const immunizations = workspace?.patient_dashboard.database.immunizations ?? [];
  const hospitalizations =
    workspace?.patient_dashboard.database.hospitalizations ?? [];
  const laboratoryResults =
    workspace?.patient_dashboard.database.laboratory_results ?? [];
  const diagnoses = workspace?.medical_workspace.diagnoses ?? [];
  const problems = workspace?.medical_workspace.problems ?? [];

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 px-5 py-12 sm:px-8">
      <section className="glass-panel p-8 sm:p-10">
        <span className="chip">Doctor workspace</span>
        <h1 className="mt-6 font-[family:var(--font-versa-display)] text-5xl leading-[0.96] tracking-tight text-slate-950">
          Manage assigned patients with records, history, and analyzer runs.
        </h1>
        <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-600">
          Click a patient to review their HIS-backed record, longitudinal medical
          history, and upload new lab data or files into the diagnosis analysis
          pipeline.
        </p>
      </section>

      <section className="grid gap-6 xl:grid-cols-[24rem_minmax(0,1fr)]">
        <aside className="space-y-6">
          <div className="glass-panel p-8">
            <form className="space-y-5" onSubmit={handleAssignPatient} noValidate>
              <div className="space-y-2">
                <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                  Patient lookup
                </p>
                <h2 className="text-3xl font-semibold tracking-tight text-slate-950">
                  Assign a patient
                </h2>
              </div>

              <div className="grid gap-4">
                <Field
                  name="egn"
                  label="EGN"
                  placeholder="9001010000"
                  inputMode="numeric"
                  error={fieldError(fieldErrors, "egn")}
                />
                <Field
                  name="firstName"
                  label="First name"
                  placeholder="Ivan"
                  error={fieldError(fieldErrors, "first_name")}
                />
                <Field
                  name="middleName"
                  label="Middle name"
                  placeholder="Petrov"
                  error={fieldError(fieldErrors, "middle_name")}
                />
                <Field
                  name="lastName"
                  label="Last name"
                  placeholder="Ivanov"
                  error={fieldError(fieldErrors, "last_name", "non_field_errors")}
                />
              </div>

              {formError ? <p className="error-banner">{formError}</p> : null}

              <button
                type="submit"
                className="primary-button w-full px-6 py-3 text-base disabled:cursor-not-allowed disabled:opacity-70"
                disabled={isSubmittingAssignment}
              >
                {isSubmittingAssignment ? "Assigning..." : "Assign patient"}
              </button>
            </form>
          </div>

          <div className="glass-panel p-8">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                  Assigned list
                </p>
                <h2 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950">
                  Linked patients
                </h2>
              </div>
              <span className="chip">{assignments.length}</span>
            </div>

            {isFetchingAssignments ? (
              <div className="mt-6 space-y-3">
                <div className="h-24 animate-pulse rounded-[24px] bg-white/70" />
                <div className="h-24 animate-pulse rounded-[24px] bg-white/70" />
              </div>
            ) : assignments.length ? (
              <div className="mt-6 space-y-3">
                {assignments.map((assignment) => {
                  const isSelected = assignment.id === selectedAssignmentId;

                  return (
                    <button
                      key={assignment.id}
                      type="button"
                      onClick={() => {
                        setSelectedAssignmentId(assignment.id);
                        setSubmissionError(null);
                        setSubmissionSuccess(null);
                      }}
                      className={`w-full rounded-[24px] border p-5 text-left transition ${
                        isSelected
                          ? "border-teal-300 bg-teal-50/80 shadow-[0_12px_28px_rgba(14,115,111,0.12)]"
                          : "border-white/60 bg-white/72 shadow-[inset_0_1px_0_rgba(255,255,255,0.88)]"
                      }`}
                    >
                      <h3 className="text-lg font-semibold text-slate-950">
                        {assignment.patient.first_name} {assignment.patient.middle_name}{" "}
                        {assignment.patient.last_name}
                      </h3>
                      <div className="mt-3 space-y-1 text-sm text-slate-600">
                        <p>EGN: {assignment.patient.egn}</p>
                        <p>Birth date: {assignment.patient.birth_date}</p>
                        <p>Username: {assignment.patient.user.username}</p>
                      </div>
                    </button>
                  );
                })}
              </div>
            ) : (
              <p className="mt-6 text-sm leading-7 text-slate-600">
                No patients are assigned to this doctor yet.
              </p>
            )}
          </div>
        </aside>

        <section className="space-y-6">
          {workspaceError ? <p className="error-banner">{workspaceError}</p> : null}

          {!selectedAssignmentId ? (
            <div className="glass-panel p-10">
              <h2 className="text-3xl font-semibold tracking-tight text-slate-950">
                Select a patient to open the workspace.
              </h2>
              <p className="mt-4 max-w-2xl text-base leading-8 text-slate-600">
                Once a patient is assigned, you can open their HIS record,
                medical history, and submission panel from here.
              </p>
            </div>
          ) : isFetchingWorkspace || !workspace ? (
            <div className="glass-panel p-10">
              <div className="h-6 w-40 animate-pulse rounded-full bg-teal-100" />
              <div className="mt-6 h-16 w-2/3 animate-pulse rounded-3xl bg-slate-200" />
              <div className="mt-10 h-80 animate-pulse rounded-[28px] bg-white/70" />
            </div>
          ) : (
            <>
              <section className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
                <article className="glass-panel p-8 sm:p-10">
                  <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                    Selected patient
                  </p>
                  <h2 className="mt-4 text-4xl font-semibold tracking-tight text-slate-950">
                    {selectedPatient?.full_name}
                  </h2>
                  <p className="mt-4 max-w-2xl text-base leading-8 text-slate-600">
                    HIS-linked identity, medical history, and new submissions for{" "}
                    {selectedPatient?.full_name} live in this workspace.
                  </p>
                  <div className="mt-6 grid gap-3 md:grid-cols-2">
                    <StatCard label="EGN" value={selectedPatient?.egn ?? "Not available"} />
                    <StatCard
                      label="Blood type"
                      value={selectedPatient?.blood_type ?? "Not available"}
                    />
                    <StatCard
                      label="Gender"
                      value={selectedPatient?.gender ?? "Not available"}
                    />
                    <StatCard
                      label="Birth date"
                      value={selectedPatient?.birth_date ?? "Not available"}
                    />
                  </div>
                </article>

                <article className="glass-panel p-8">
                  <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                    Coverage
                  </p>
                  <div className="mt-5 space-y-3 text-sm text-slate-600">
                    <Detail
                      label="Immunizations"
                      value={String(immunizations.length)}
                    />
                    <Detail
                      label="Hospitalizations"
                      value={String(hospitalizations.length)}
                    />
                    <Detail
                      label="Diagnoses"
                      value={String(diagnoses.length)}
                    />
                    <Detail
                      label="Tracked problems"
                      value={String(problems.length)}
                    />
                    <Detail
                      label="Lab submissions"
                      value={String(laboratoryResults.length)}
                    />
                  </div>
                </article>
              </section>

              <section className="grid gap-6 2xl:grid-cols-[1.02fr_0.98fr]">
                <article className="glass-panel p-8 sm:p-10">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                        Medical history
                      </p>
                      <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
                        HIS and longitudinal record
                      </h2>
                    </div>
                    <span className="chip">
                      {immunizations.length + hospitalizations.length} synced items
                    </span>
                  </div>

                  <div className="mt-8 space-y-6">
                    <HistoryGroup
                      title="Immunizations"
                      emptyText="No immunization history is currently synced."
                    >
                      {immunizations.map((item) => (
                        <HistoryCard
                          key={`${item.vaccine_name}-${item.date}-${item.dose_number}`}
                          title={item.vaccine_name}
                          lines={[
                            `Dose ${item.dose_number}`,
                            item.date,
                            item.institution,
                          ]}
                        />
                      ))}
                    </HistoryGroup>

                    <HistoryGroup
                      title="Hospitalizations"
                      emptyText="No hospitalization history is currently synced."
                    >
                      {hospitalizations.map((item) => (
                        <div
                          key={`${item.diagnosis_code}-${item.admission_date}`}
                          className="rounded-[24px] border border-white/60 bg-white/74 p-5"
                        >
                          <h3 className="text-lg font-semibold text-slate-950">
                            {item.diagnosis}
                          </h3>
                          <p className="mt-2 text-sm text-slate-500">
                            {item.diagnosis_code} | {item.department} | {item.institution}
                          </p>
                          <p className="mt-3 text-sm text-slate-700">
                            {item.admission_date} to {item.discharge_date ?? "ongoing"}
                          </p>
                          {item.epicrisis ? (
                            <div className="mt-4 rounded-[20px] bg-teal-50/80 p-4">
                              <p className="text-xs uppercase tracking-[0.22em] text-teal-700">
                                Epicrisis summary
                              </p>
                              <p className="mt-2 text-sm leading-7 text-slate-700">
                                {item.epicrisis.summary}
                              </p>
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </HistoryGroup>

                    <HistoryGroup
                      title="Lab submissions"
                      emptyText="No doctor-submitted laboratory runs are linked yet."
                    >
                      {laboratoryResults.map((result) => (
                        <LabRunCard key={result.id} result={result} />
                      ))}
                    </HistoryGroup>
                  </div>
                </article>

                <div className="space-y-6">
                  <article className="glass-panel p-8 sm:p-10">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                          Analyzer submission
                        </p>
                        <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
                          Submit a new lab run
                        </h2>
                      </div>
                      <span className="chip">AI-ready</span>
                    </div>

                    <form
                      className="mt-8 space-y-4"
                      onSubmit={handleWorkspaceSubmit}
                      noValidate
                    >
                      <div className="grid gap-4 md:grid-cols-2">
                        <Field
                          name="laboratoryRequest"
                          label="Lab request ID"
                          value={submissionState.laboratoryRequest}
                          onChange={(value) =>
                            setSubmissionState((current) => ({
                              ...current,
                              laboratoryRequest: value,
                            }))
                          }
                        />
                        <Field
                          name="laboratoryName"
                          label="Laboratory name"
                          value={submissionState.laboratoryName}
                          onChange={(value) =>
                            setSubmissionState((current) => ({
                              ...current,
                              laboratoryName: value,
                            }))
                          }
                        />
                      </div>

                      <div className="grid gap-4 md:grid-cols-2">
                        <Field
                          name="collectedAt"
                          label="Collected at"
                          type="datetime-local"
                          value={submissionState.collectedAt}
                          onChange={(value) =>
                            setSubmissionState((current) => ({
                              ...current,
                              collectedAt: value,
                            }))
                          }
                        />
                        <Field
                          name="reportedAt"
                          label="Reported at"
                          type="datetime-local"
                          value={submissionState.reportedAt}
                          onChange={(value) =>
                            setSubmissionState((current) => ({
                              ...current,
                              reportedAt: value,
                            }))
                          }
                        />
                      </div>

                      <div className="grid gap-4 md:grid-cols-2">
                        <SelectField
                          label="Diagnosis kind"
                          value={submissionState.diagnosisKind}
                          onChange={(value) =>
                            setSubmissionState((current) => ({
                              ...current,
                              diagnosisKind: value,
                            }))
                          }
                          options={[
                            ["blood_test", "Blood test"],
                            ["radiology", "Radiology"],
                            ["physical_exam", "Physical exam"],
                            ["doctor_diagnosis", "Doctor diagnosis"],
                            ["user_note", "Clinical note"],
                            ["other", "Other"],
                          ]}
                        />
                        <Field
                          name="happenedAt"
                          label="Clinical date"
                          type="date"
                          value={submissionState.happenedAt}
                          required={false}
                          onChange={(value) =>
                            setSubmissionState((current) => ({
                              ...current,
                              happenedAt: value,
                            }))
                          }
                        />
                      </div>

                      <Field
                        name="title"
                        label="Submission title"
                        value={submissionState.title}
                        onChange={(value) =>
                          setSubmissionState((current) => ({
                            ...current,
                            title: value,
                          }))
                        }
                      />

                      <TextAreaField
                        label="Structured test results JSON"
                        value={submissionState.testResults}
                        onChange={(value) =>
                          setSubmissionState((current) => ({
                            ...current,
                            testResults: value,
                          }))
                        }
                      />

                      <TextAreaField
                        label="Clinical note or interpretation"
                        value={submissionState.rawText}
                        onChange={(value) =>
                          setSubmissionState((current) => ({
                            ...current,
                            rawText: value,
                          }))
                        }
                        rows={5}
                      />

                      <TextAreaField
                        label="Extra raw JSON context"
                        value={submissionState.rawJson}
                        onChange={(value) =>
                          setSubmissionState((current) => ({
                            ...current,
                            rawJson: value,
                          }))
                        }
                        rows={4}
                      />

                      <label className="space-y-2">
                        <span className="text-sm font-medium text-slate-700">
                          Attachments
                        </span>
                        <input
                          type="file"
                          multiple
                          accept=".pdf,.png,.jpg,.jpeg,.webp,.dcm"
                          className="field-input cursor-pointer"
                          onChange={(event) =>
                            setSelectedFiles(Array.from(event.target.files ?? []))
                          }
                        />
                        <p className="text-sm text-slate-500">
                          {selectedFiles.length
                            ? `${selectedFiles.length} file(s) selected`
                            : "Upload scans, PDFs, or supporting lab images."}
                        </p>
                      </label>

                      {submissionError ? (
                        <p className="error-banner">{submissionError}</p>
                      ) : null}
                      {submissionSuccess ? (
                        <p className="rounded-[20px] border border-teal-200 bg-teal-50/85 p-4 text-sm text-teal-800">
                          {submissionSuccess}
                        </p>
                      ) : null}

                      <button
                        type="submit"
                        className="primary-button w-full px-6 py-3 text-base disabled:cursor-not-allowed disabled:opacity-70"
                        disabled={isSubmittingWorkspace}
                      >
                        {isSubmittingWorkspace
                          ? "Submitting to analyzer..."
                          : "Submit run and analyze"}
                      </button>
                    </form>
                  </article>

                  <article className="glass-panel p-8 sm:p-10">
                    <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                      Analysis memory
                    </p>
                    <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
                      Diagnoses and tracked problems
                    </h2>

                    <div className="mt-8 space-y-6">
                      <HistoryGroup
                        title="Diagnoses"
                        emptyText="No analyzed diagnoses have been stored yet."
                      >
                        {diagnoses.map((diagnosis) => (
                          <div
                            key={diagnosis.id}
                            className="rounded-[24px] border border-white/60 bg-white/74 p-5"
                          >
                            <div className="flex items-center justify-between gap-4">
                              <h3 className="text-lg font-semibold text-slate-950">
                                {diagnosis.title}
                              </h3>
                              <span className="chip">
                                {diagnosis.kind.replaceAll("_", " ")}
                              </span>
                            </div>
                            <p className="mt-3 text-sm leading-7 text-slate-700">
                              {diagnosis.summary || diagnosis.description || "No summary yet."}
                            </p>
                            {diagnosis.keywords.length ? (
                              <div className="mt-4 flex flex-wrap gap-2">
                                {diagnosis.keywords.map((keyword) => (
                                  <span
                                    key={`${diagnosis.id}-${keyword}`}
                                    className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
                                  >
                                    {keyword}
                                  </span>
                                ))}
                              </div>
                            ) : null}
                          </div>
                        ))}
                      </HistoryGroup>

                      <HistoryGroup
                        title="Tracked problems"
                        emptyText="No persistent problems have been linked yet."
                      >
                        {problems.map((problem) => (
                          <div
                            key={problem.id}
                            className="rounded-[24px] border border-white/60 bg-white/74 p-5"
                          >
                            <h3 className="text-lg font-semibold text-slate-950">
                              {problem.title}
                            </h3>
                            <p className="mt-3 text-sm leading-7 text-slate-700">
                              {problem.summary}
                            </p>
                          </div>
                        ))}
                      </HistoryGroup>
                    </div>
                  </article>
                </div>
              </section>
            </>
          )}
        </section>
      </section>
    </main>
  );
}

function Field({
  name,
  label,
  error,
  placeholder,
  inputMode,
  type = "text",
  value,
  onChange,
  required,
}: {
  name: string;
  label: string;
  error?: string | null;
  placeholder?: string;
  inputMode?: HTMLAttributes<HTMLInputElement>["inputMode"];
  type?: InputHTMLAttributes<HTMLInputElement>["type"];
  value?: string;
  onChange?: (value: string) => void;
  required?: boolean;
}) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        name={name}
        type={type}
        className={inputClassName(Boolean(error))}
        placeholder={placeholder}
        inputMode={inputMode}
        required={required ?? true}
        value={value}
        onChange={onChange ? (event) => onChange(event.target.value) : undefined}
      />
      {error ? <p className="error-text">{error}</p> : null}
    </label>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<[string, string]>;
}) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <select
        className="field-input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </select>
    </label>
  );
}

function TextAreaField({
  label,
  value,
  onChange,
  rows = 7,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
}) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <textarea
        className="field-input min-h-[8rem] resize-y"
        rows={rows}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span>{label}</span>
      <span className="text-right font-medium text-slate-900">{value}</span>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[22px] border border-white/60 bg-white/82 p-4">
      <p className="text-xs uppercase tracking-[0.22em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm font-medium text-slate-900">{value}</p>
    </div>
  );
}

function HistoryGroup({
  title,
  emptyText,
  children,
}: {
  title: string;
  emptyText: string;
  children: ReactNode;
}) {
  const childCount = Array.isArray(children) ? children.length : children ? 1 : 0;

  return (
    <section>
      <div className="flex items-center justify-between gap-4">
        <h3 className="text-xl font-semibold text-slate-950">{title}</h3>
        <span className="chip">{childCount}</span>
      </div>
      {childCount ? (
        <div className="mt-4 space-y-4">{children}</div>
      ) : (
        <p className="mt-4 text-sm leading-7 text-slate-600">{emptyText}</p>
      )}
    </section>
  );
}

function HistoryCard({
  title,
  lines,
}: {
  title: string;
  lines: string[];
}) {
  return (
    <div className="rounded-[24px] border border-white/60 bg-white/74 p-5">
      <h4 className="text-lg font-semibold text-slate-950">{title}</h4>
      <div className="mt-3 space-y-1 text-sm text-slate-600">
        {lines.map((line) => (
          <p key={`${title}-${line}`}>{line}</p>
        ))}
      </div>
    </div>
  );
}

function LabRunCard({ result }: { result: LaboratoryResultSummary }) {
  return (
    <div className="rounded-[24px] border border-white/60 bg-white/74 p-5">
      <div className="flex items-center justify-between gap-4">
        <h4 className="text-lg font-semibold text-slate-950">Run {result.id.slice(0, 8)}</h4>
        <span className="chip">{result.status}</span>
      </div>
      <p className="mt-3 text-sm leading-7 text-slate-700">{result.summary}</p>
      {result.attachments.length ? (
        <p className="mt-3 text-sm text-slate-500">
          Attachments: {result.attachments.map((item) => item.title).join(", ")}
        </p>
      ) : null}
    </div>
  );
}
