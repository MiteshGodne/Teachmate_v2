function Use() {
  const cardData = [
    {
      step: 1,
      heading: "Upload Presentation",
      desc: "Start by clicking the upload button to select your PowerPoint file. Once uploaded, your presentation will be automatically converted into a high-quality MP4 video.",
    },
    {
      step: 2,
      heading: "Convert and View",
      desc: "Easily convert your PowerPoint presentation into an MP4 video and view the final output. Play the converted video to ensure everything looks just right before sharing or downloading.",
    },
    {
      step: 3,
      heading: "Save and Download",
      desc: "Once your presentation is converted, simply click the download button to save your MP4 video. TechMate processes the file instantly, giving you a ready-to-use video in just a few seconds.",
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
