import { useState } from "react";
import "../css/Contact.css";

const ACCESS_KEY = import.meta.env.VITE_WEB3FORMS_KEY;

const Contact = () => {
  const [status, setStatus] = useState("idle"); // idle | sending | sent | error

  const onSubmit = async (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    setStatus("sending");
    try {
      if (!ACCESS_KEY) throw new Error("missing key");
      const data = new FormData(form);
      data.append("access_key", ACCESS_KEY);
      const res = await fetch("https://api.web3forms.com/submit", {
        method: "POST",
        headers: { Accept: "application/json" },
        body: data,
      });
      const json = await res.json();
      if (!json.success) throw new Error(json.message);
      form.reset();
      setStatus("sent");
    } catch {
      setStatus("error");
    }
  };

  return (
    <div className="contact-container">
      <h2>Contact Us</h2>
      <form onSubmit={onSubmit} className="contact-form">
        <input type="checkbox" name="botcheck" style={{ display: "none" }} tabIndex={-1} autoComplete="off" />
        <div className="form-group">
          <label htmlFor="name">Name</label>
          <input type="text" id="name" name="name" required placeholder="Your Name" />
        </div>
        <div className="form-group">
          <label htmlFor="email">Email</label>
          <input type="email" id="email" name="email" required placeholder="Your Email" />
        </div>
        <div className="form-group">
          <label htmlFor="message">Message</label>
          <textarea id="message" name="message" required placeholder="Your Message" />
        </div>
        <button type="submit" className="submit-btn" disabled={status === "sending"}>
          {status === "sending" ? "Sending…" : "Send Message"}
        </button>
        {status === "sent" && <p className="form-status ok" role="status">Thanks! Your message was sent.</p>}
        {status === "error" && <p className="form-status err" role="alert">Something went wrong. Please try again.</p>}
      </form>
    </div>
  );
};

export default Contact;