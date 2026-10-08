import "./css/index.css";
import { createBrowserRouter, Link, Outlet, RouterProvider } from "react-router-dom";
import Home from "./components/Home";
import About from "./components/About";
import Contact from "./components/Contact";
import Navbar from "./components/Navbar";
import Upload from "./components/Upload";
import Use from "./components/Use";
import Footer from "./components/Footer";

const Layout = () => (
  <>
    <Navbar />
    <main>
      <Outlet />
    </main>
    <Footer />
  </>
);

const NotFound = () => (
  <div className="main-container">
    <h1>404</h1>
    <p>That page doesn't exist.</p>
    <Link to="/" className="btn btn-primary">Back home</Link>
  </div>
);

// Created once, outside the component. Before, it was rebuilt on every render.
const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: <><Home /><Use /></> },
      { path: "/about", element: <About /> },
      { path: "/contact", element: <Contact /> },
      { path: "/upload", element: <Upload /> },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}