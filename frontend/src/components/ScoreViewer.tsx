interface Props {
  url: string;
}

export default function ScoreViewer({ url }: Props) {
  return (
    <div className="score-viewer">
      <img
        src={url}
        alt="Score"
        style={{ width: '100%', display: 'block' }}
        onError={(e) => {
          const el = e.currentTarget;
          el.style.display = 'none';
          const msg = document.createElement('p');
          msg.className = 'score-status score-status--error';
          msg.textContent = 'Score not available.';
          el.parentElement?.appendChild(msg);
        }}
      />
    </div>
  );
}
