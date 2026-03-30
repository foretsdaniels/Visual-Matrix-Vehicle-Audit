import { UploadForm } from "@/components/upload-form"

export default function HomePage() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-foreground">Generate Parking Audit</h1>
        <p className="text-muted-foreground">
          Upload the Visual Matrix In-House Guests export to generate label previews and reports.
        </p>
      </div>
      
      <UploadForm />
    </div>
  )
}
