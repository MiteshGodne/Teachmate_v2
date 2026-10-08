import { Link } from "react-router-dom";
import "../css/Footer.css";

const Footer = () => (
  <footer className="footer">
    <div className="footer-container">
      <div className="footer-brand">
        <h2>Teach-Mate</h2>
        <p>Convert your PowerPoint presentations to videos.</p>
      </div>

      <div className="footer-links">
        <h4>Quick Links</h4>
        <ul>
          <li><Link to="/">Home</Link></li>
          <li><Link to="/upload">Upload</Link></li>
          <li><Link to="/about">About</Link></li>
          <li><Link to="/contact">Contact</Link></li>
        </ul>
      </div>

      <div className="footer-social">
        <h4>Source</h4>
        <div className="social-icons">
          <a href="https://github.com/MiteshGodne/teachmate_v2" target="_blank" rel="noopener noreferrer">GitHub</a>
        </div>
      </div>
    </div>

    <div className="footer-bottom">
      <p>&copy; {new Date().getFullYear()} Teach-Mate. All rights reserved.</p>
    </div>
  </footer>
);

export default Footer;