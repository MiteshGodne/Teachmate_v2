
import "../css/Contact.css";

const Contact = () => {
 



  return (
    <div className="contact-container">
      <h2 >Contact Us</h2>
      <form action="https://api.web3forms.com/submit" method="POST"  className="contact-form">
        <div className="form-group">
          
          <label htmlFor="name">Name</label>
          <input type="hidden" name="access_key" value="62b50ba4-1f85-4441-91be-383c1cdbdb35"></input>
          <input
            type="text"
            id="name"
            name="name"
            required
            placeholder="Your Name"
          />
        </div>

        <div className="form-group">
          <label htmlFor="email">Email</label>
          <input
            type="email"
            id="email"
            name="email"
        
            required
            placeholder="Your Email"
          />
        </div>

        <div className="form-group">
          <label htmlFor="message">Message</label>
          <textarea
            id="message"
            name="message"
          
            required
            placeholder="Your Message"
          ></textarea>
        </div>

        <button type="submit" className="submit-btn">Send Message</button>
      </form>
    </div>
  );
};

export default Contact;
