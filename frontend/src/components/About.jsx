import "../css/About.css";

const AUTHOR = {
  name: "Mitesh Godne",
  github: "https://github.com/MiteshGodne/teachmate_v2",
};

const features = [
  ["Many formats", "PPTX, PPT, PPSX, ODP and PDF. Legacy files are converted automatically."],
  ["Smart narration", "Uses your speaker notes first, falls back to slide text. Empty slides stay silent."],
  ["Six languages", "English, Hindi, Marathi, Spanish, French and German voices."],
  ["Subtitles included", "Download an .srt file synced to the narration."],
  ["Private by default", "Your upload is deleted as soon as processing ends; results expire after about an hour."],
];

const stack = ["React + Vite", "FastAPI", "LibreOffice", "FFmpeg", "edge-tts / gTTS", "Redis" , "Docker"];

const About = () => (
  <div className="about-container">
    <section className="hero-section">
      <h1>About TeachMate ~</h1>
      <p>
        TeachMate turns ppts or pdfs into narrated MP4 lectures. It was built to help
        educators publish video lessons without recording anything.
      </p>
    </section>

    <section>
      <h2>What it does ?</h2>
      <div className="feature-grid">
        {features.map(([title, text]) => (
          <div className="feature" key={title}>
            <h3>{title}</h3>
            <p>{text}</p>
          </div>
        ))}
      </div>
    </section>

    <section>
      <h2>Built with ~</h2>
      <ul className="stack">
        {stack.map((s) => <li key={s}>{s}</li>)}
      </ul>
    </section>

    <section>
      <h2>Who built it ?</h2>
      <p>
        Designed and Developed by {AUTHOR.name}. {" "}
        <a href={AUTHOR.github} target="_blank" rel="noopener noreferrer">View the source on GitHub</a>.
      </p>
    </section>
  </div>
);

export default About;