
const VideoPlayer = ({ videoUrl }) => {
  return (
    <div className="flex justify-center items-center h-full p-4">
      <video
        controls
        className="rounded-2xl shadow-lg max-w-full max-h-[80vh]"
      >
        <source src={videoUrl} type="video/mp4" />
        Your browser does not support the video tag.
      </video>
    </div>
  );
};

export default VideoPlayer;
