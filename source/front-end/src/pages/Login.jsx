import { useState } from "react";
import api from "../api";
import { setToken } from "../auth";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");

  const onSubmit = async (e) => {
    e.preventDefault();
    setErr("");
    try {
      // 1. Login
      const { data } = await api.post("/auth/login", { email, password });
      setToken(data.session_token);

      // 2. Fetch user profile to know their id
      const { data: user } = await api.get("/auth/me");

      // 3. Save user id in localStorage
      localStorage.setItem("current_user_id", user.id);

      // 4. Make sure chat_id for this user is fresh
      localStorage.removeItem(`chat_id_${user.id}`);

      // 5. Redirect to chat
      window.location.href = "/";
    } catch (e) {
      setErr(e?.response?.data?.detail || "Login failed");
    }
  };

  return (
    <div className="min-h-screen w-screen flex items-center justify-center bg-gray-900">
      <div className="w-full max-w-sm rounded-xl bg-gray-800/80 backdrop-blur p-6 shadow-xl">
        <h1 className="text-white text-3xl font-bold mb-6">Login</h1>

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-300 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e)=>setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full px-3 py-2 rounded-lg bg-gray-700 text-white
                         focus:outline-none focus:ring-2 focus:ring-sky-500"
              required
            />
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e)=>setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-3 py-2 rounded-lg bg-gray-700 text-white
                         focus:outline-none focus:ring-2 focus:ring-sky-500"
              required
            />
          </div>

          {err && <div className="text-sm text-red-400">{err}</div>}

          <button
            type="submit"
            className="w-full py-2 rounded-lg bg-sky-600 hover:bg-sky-700
                       text-white font-semibold"
          >
            Sign in
          </button>
        </form>

        <p className="mt-4 text-sm text-gray-400 text-center">
          No account? <a href="/signup" className="text-sky-400 hover:underline">Create one</a>
        </p>
      </div>
    </div>
  );
}
