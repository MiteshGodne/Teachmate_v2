import { Link } from "react-router-dom";          // was "react-router"
import "../css/Home.css"; // Add this line
function Home() {
  return (
    <div className="main-container">
      <h1>
        Convert PowerPoint to <span className="span">MP4</span>
      </h1>
      <p>Save PPT as MP4 Effortlessly with Teach-mate.</p>
      <div className="button-container">
        <Link to="/upload" className="button btn btn-primary">Get Started</Link>
        <Link to="/about" className="button btn-secondary btn">Learn More</Link>   
      </div>

      <div className="hero">
        <img
          src="https://images.unsplash.com/photo-1502209877429-d7c6df9eb3f9?q=80&w=2932&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D"
          className="hero-img"
          alt="Convert PPT to video illustration"
        />
      </div>
    </div>
  );
}
export default Home;
