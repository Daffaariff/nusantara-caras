import { useState } from "react";
import api from "../api";
import { setToken } from "../auth";

export default function Signup() {
  const [email, setEmail] = useState("");
  const [display_name, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [date_of_birth, setDob] = useState("");
  const [address_line1, setAddr1] = useState("");
  const [address_line2, setAddr2] = useState("");
  const [city, setCity] = useState("");
  const [province, setProvince] = useState("");
  const [postal_code, setPostal] = useState("");
  const [gender, setGender] = useState("");
  const [err, setErr] = useState("");

  const onSubmit = async (e) => {
    e.preventDefault();
    setErr("");
    try {
      const { data } = await api.post("/auth/signup", {
        email,
        display_name,
        password,
        date_of_birth,     // must be format YYYY-MM-DD
        address_line1,
        address_line2: address_line2 || null,
        city,
        province,
        postal_code,
        gender,
      });
      setToken(data.session_token);
      window.location.href = "/";
    } catch (e) {
      setErr(e?.response?.data?.detail || "Signup failed");
    }
  };

  return (
    <div className="min-h-screen w-screen flex items-center justify-center bg-gray-900">
      <div className="w-full max-w-md rounded-xl bg-gray-800/80 backdrop-blur p-6 shadow-xl">
        <h1 className="text-white text-3xl font-bold mb-6">Create Account</h1>

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-300 mb-1">Email</label>
            <input type="email" value={email} onChange={e=>setEmail(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
              placeholder="you@example.com" required />
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-1">Display Name</label>
            <input value={display_name} onChange={e=>setDisplayName(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
              placeholder="Your name" required />
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-1">Password</label>
            <input type="password" value={password} onChange={e=>setPassword(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
              placeholder="••••••••" required />
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-1">Date of Birth</label>
            <input type="date" value={date_of_birth} onChange={e=>setDob(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
              required />
          </div>

          {/* Gender */}
          <div>
            <label className="block text-sm text-gray-300 mb-1">Gender</label>
            <select value={gender} onChange={e=>setGender(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
              required>
              <option value="">Select gender</option>
              <option value="Male">Male</option>
              <option value="Female">Female</option>
              <option value="Other">Other</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-1">Address</label>
            <input value={address_line1} onChange={e=>setAddr1(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
              placeholder="Street / RT/RW" required />
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-1">Address Line 2 (optional)</label>
            <input value={address_line2} onChange={e=>setAddr2(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
              placeholder="Apartment, block, etc." />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="block text-sm text-gray-300 mb-1">City</label>
              <input value={city} onChange={e=>setCity(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
                required />
            </div>
            <div>
              <label className="block text-sm text-gray-300 mb-1">Postal Code</label>
              <input value={postal_code} onChange={e=>setPostal(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
                required />
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-1">Province</label>
            <input value={province} onChange={e=>setProvince(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
              required />
          </div>

          {err && <div className="text-sm text-red-400">{err}</div>}

          <button type="submit"
            className="w-full py-2 rounded-lg bg-sky-600 hover:bg-sky-700 text-white font-semibold">
            Sign Up
          </button>
        </form>

        <p className="mt-4 text-sm text-gray-400 text-center">
          Already have an account?{" "}
          <a href="/login" className="text-sky-400 hover:underline">Sign in</a>
        </p>
      </div>
    </div>
  );
}
