import "../css/About.css";

const teamMembers = [
  {
    name: "Mitesh Godne",
    role: "Full Stack Developer",
    image: "https://avatars.githubusercontent.com/u/129673121?v=",
  },
];

const About = () => {
  return (
    <div className="about-container">
      {/* Hero Section */}
      <section className="hero-section">
        <h1>About Us</h1>
        <p>
          We are a tech-driven team building a smart tool that converts
          PowerPoint presentations into MP4 videos with audioscript. Our goal is
          to make content creation faster, easier, and more accessible for
          educators and professionals.
        </p>
      </section>

      {/* Team Section */}
      <section className="team-section">
        <h2>Meet Our Team</h2>
        <div className="team-grid">
          {teamMembers.map((member, index) => (
            <div className="team-member" key={index}>
              <img src={member.image} alt={`${member.name}`} />
              <h3>{member.name}</h3>
              <p>{member.role}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Mission Section */}
      <section className="mission-section">
        <h2>Our Mission</h2>
        <p>
          To simplify and automate the creation of video lectures by converting
          PowerPoint presentations into engaging MP4 videos with audioscript ,
          making content delivery easier, faster, and more accessible for
          educators and learners.
        </p>
      </section>
    </div>
  );
};

export default About;
