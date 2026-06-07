import { PatientProblemDetail } from "@/components/patient-problem-detail";

type PatientProblemPageProps = {
  params: Promise<{
    problemId: string;
  }>;
};

export default async function PatientProblemPage({ params }: PatientProblemPageProps) {
  const { problemId } = await params;

  return <PatientProblemDetail problemId={problemId} />;
}
