export function DisclaimerBanner({ text }: { text: string }) {
  return (
    <div className="disclaimer" role="note">
      {text}
    </div>
  );
}
