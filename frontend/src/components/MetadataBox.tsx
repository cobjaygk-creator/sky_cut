export function MetadataBox({
  copiedKey,
  idPrefix,
  titleCandidates,
  description,
  hashtags,
  onCopyText,
}: {
  copiedKey: string | null;
  idPrefix: string;
  titleCandidates: string[];
  description: string;
  hashtags: string[];
  onCopyText: (key: string, text: string) => void;
}) {
  const hashtagText = hashtags.join(" ");
  return (
    <div className="metadata-box">
      <div className="metadata-section">
        <span>제목</span>
        {titleCandidates.map((title, index) => (
          <div className="copy-row" key={`${idPrefix}-title-${index}`}>
            <p>{title}</p>
            <button className="copy-button" type="button" onClick={() => onCopyText(`${idPrefix}-title-${index}`, title)}>
              {copiedKey === `${idPrefix}-title-${index}` ? "복사됨" : "복사"}
            </button>
          </div>
        ))}
      </div>
      <div className="metadata-section">
        <span>설명</span>
        <div className="copy-row">
          <p>{description}</p>
          <button className="copy-button" type="button" onClick={() => onCopyText(`${idPrefix}-description`, description)}>
            {copiedKey === `${idPrefix}-description` ? "복사됨" : "복사"}
          </button>
        </div>
      </div>
      <div className="metadata-section">
        <span>해시태그</span>
        <div className="copy-row">
          <p>{hashtagText}</p>
          <button className="copy-button" type="button" onClick={() => onCopyText(`${idPrefix}-hashtags`, hashtagText)}>
            {copiedKey === `${idPrefix}-hashtags` ? "복사됨" : "복사"}
          </button>
        </div>
      </div>
    </div>
  );
}
