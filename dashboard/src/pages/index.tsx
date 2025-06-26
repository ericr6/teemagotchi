import EmotionBars from "@/components/EmotionBars";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center p-8">
      <h1 className="text-2xl font-bold mb-4">Team mood (live)</h1>
      <EmotionBars />
    </main>
  );
}
