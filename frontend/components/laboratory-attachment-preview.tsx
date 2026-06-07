"use client";

import {
  laboratoryAttachmentDownloadUrl,
  laboratoryAttachmentPreviewUrl,
  type LaboratoryAttachment,
} from "@/lib/auth-client";

export function LaboratoryAttachmentPreview({
  attachment,
}: {
  attachment: LaboratoryAttachment;
}) {
  const previewUrl = laboratoryAttachmentPreviewUrl(attachment.id);
  const canPreview = attachment.file_type === "image" || attachment.file_type === "pdf";

  return (
    <article className="w-full overflow-hidden rounded-[22px] border border-slate-200 bg-white">
      <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-950">{attachment.title}</p>
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
            {attachment.file_type}
          </p>
        </div>
        <a
          href={laboratoryAttachmentDownloadUrl(attachment.id)}
          className="secondary-button shrink-0 px-3 py-2 text-xs"
        >
          Download
        </a>
      </div>

      {canPreview ? (
        <iframe
          src={previewUrl}
          title={attachment.title}
          className="h-[420px] w-full bg-slate-100"
        />
      ) : (
        <div className="flex min-h-40 items-center justify-center p-6 text-center text-sm text-slate-600">
          This file type cannot be displayed in the browser.
        </div>
      )}
    </article>
  );
}
