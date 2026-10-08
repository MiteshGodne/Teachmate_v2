const VideoPlayer = ({ videoUrl }) => (
  <div className="video-wrap">
    <video key={videoUrl} className="video-el" controls preload="metadata" src={videoUrl}>
      Your browser does not support the video tag.
    </video>
  </div>
);
export default VideoPlayer;
