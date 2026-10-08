function Use() {
  const cardData = [
    {
      step: 1, heading: "Upload Presentation",
      desc: "Upload a .pptx, .ppt, .ppsx, .odp or PDF file, then choose a narration language and whether to read speaker notes or slide text."
    },
    {
      step: 2, heading: "Convert and View",
      desc: "Teach-Mate renders each slide, narrates it, and builds the MP4. You can watch live progress and preview the result in the browser."
    },
    {
      step: 3, heading: "Save and Download",
      desc: "Download the MP4 and the optional subtitle file (.srt). Processing time depends on how many slides you have."
    },
  ];
  return (
    <div className="use">
      <h2 className="use-heading">How to convert PowerPoint to MP4?</h2>
      <div className="cards">
        {cardData.map((data, i) => (
          <div className="card" key={i}>
            <div className="circle">{data.step}</div>
            <div className="card-head">{data.heading}</div>
            <div className="desc">{data.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
export default Use;
