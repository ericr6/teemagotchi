// components/EmotionBars.tsx
import { useEffect, useState } from "react";

type Emotion = { label: string; score: number };

export default function EmotionBars() {
  const [emotions, setEmotions] = useState<Emotion[]>([]);

  // poll every 3 s
  useEffect(() => {
    const tick = async () => {
      const r = await fetch("/api/emotion");
      if (r.status === 200) {
        const json = await r.json();
        setEmotions(json[0] as Emotion[]);
      }
    };
    tick();                       // first
    const id = setInterval(tick, 3000);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={{ maxWidth: 320 }}>
      {emotions.map((e) => (
        <div key={e.label} style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 12 }}>{e.label}</div>
          <div
            style={{
              height: 8,
              background: "#eee",
              borderRadius: 4,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${Math.round(e.score * 100)}%`,
                height: "100%",
                background: "#4f46e5",
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
