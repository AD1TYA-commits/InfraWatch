import ProjectDetailView from "@/components/ProjectDetailView";

export default function ProjectPage({ params }: { params: { id: string } }) {
  return <ProjectDetailView id={params.id} />;
}
