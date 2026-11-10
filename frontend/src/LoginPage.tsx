import { useState, useEffect, type ChangeEvent, type FormEvent } from "react";
import { Eye, EyeOff, ArrowLeft } from "lucide-react";
import { db } from "./client";
import { useAction } from "./useAction";

interface LoginPageProps {
  initialMode?: "signin" | "signup";
  back?: () => void;
  expiredMessage?: string;
  workspaceDestination?: string;
}

export function LoginPage({ initialMode = "signin", back, expiredMessage, workspaceDestination }: LoginPageProps) {
  const [mode, setMode] = useState<"signin" | "signup">(initialMode);
  const [showPassword, setShowPassword] = useState(false);
  const [notice, setNotice] = useState("");
  const { busy, error, run } = useAction();

  const [formData, setFormData] = useState({
    name: "",
    email: localStorage.getItem("morphy_remember_email") || "",
    password: "",
    rememberMe: !!localStorage.getItem("morphy_remember_email"),
  });

  useEffect(() => {
    setMode(initialMode);
    setNotice("");
  }, [initialMode, workspaceDestination]);

  function switchMode(next: "signin" | "signup") {
    setMode(next);
    setNotice("");
    if (!workspaceDestination) location.hash = next;
  }

  function goHome() {
    if (back) back();
    else location.hash = "";
  }

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setNotice("");

    if (formData.rememberMe && formData.email) {
      localStorage.setItem("morphy_remember_email", formData.email);
    } else {
      localStorage.removeItem("morphy_remember_email");
    }

    void run(async () => {
      if (!db) throw Error("Account sign-in is unavailable. Configure Supabase and try again.");

      const res =
        mode === "signup"
          ? await db.auth.signUp({
              email: formData.email,
              password: formData.password,
              options: {
                data: { full_name: formData.name },
                emailRedirectTo: location.origin,
              },
            })
          : await db.auth.signInWithPassword({
              email: formData.email,
              password: formData.password,
            });

      if (res.error) {
        if (
          res.error.code === "over_email_send_rate_limit" ||
          /email rate limit exceeded/i.test(res.error.message)
        ) {
          throw Error("Rate limit reached. Please wait before trying again.");
        }
        if (res.error.code === "email_address_not_authorized") {
          throw Error("Signup emails are unavailable for this address. An administrator needs to configure email delivery.");
        }
        throw res.error;
      }

      if (!res.data.session) {
        setNotice("Check your email to finish signing in.");
      }
    });
  };

  const handleForgotPassword = () => {
    if (!formData.email) {
      alert("Please enter your email address first.");
      return;
    }
    void run(async () => {
      if (!db) throw Error("Start local Supabase first.");
      const { error: resetErr } = await db.auth.resetPasswordForEmail(formData.email, {
        redirectTo: `${location.origin}/#reset`,
      });
      if (resetErr) throw resetErr;
      setNotice("Password reset instructions sent to your email.");
    });
  };

  return (
    <div className="morphy-login-scope h-screen w-screen bg-slate-900 flex overflow-hidden">
      {/* Left Panel - Image Section */}
      <div className="hidden md:flex flex-1 relative overflow-hidden">
        {/* Back Button */}
        <div className="absolute top-6 left-6 z-10">
          <button
            type="button"
            onClick={goHome}
            className="login-back-btn"
            aria-label="Back to home"
          >
            <ArrowLeft className="w-5 h-5 text-white" />
          </button>
        </div>

        <div className="absolute inset-0">
          <img
            key={mode}
            src={
              mode === "signup"
                ? "/motion/signupleftimage.jpg"
                : "https://cdn.21st.dev/assets/mirror/0d/0d205a1a31d40e927885b0ec5f603407caa10585b5bc6e8b08240402c7417e86.png"
            }
            onError={(e) => {
              e.currentTarget.src = "/motion/signupleftimage.jpg";
            }}
            alt={mode === "signup" ? "Sign Up Hero" : "Sign In Hero"}
            className="w-full h-full object-cover select-none"
          />
        </div>
      </div>

      {/* Right Panel - Form Section */}
      <div className="flex-1 flex items-center justify-center bg-white relative overflow-y-auto px-6 py-10">
        {/* Mobile Back Button */}
        <div className="md:hidden absolute top-6 left-6 z-10">
          <button
            type="button"
            onClick={goHome}
            className="login-back-btn"
            aria-label="Back to home"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
        </div>

        <div className="w-full max-w-[420px] my-auto">
          {expiredMessage && (
            <div className="mb-6 p-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-xl text-xs">
              {expiredMessage}
            </div>
          )}

          <div className="mb-7">
            <h1 className="login-title">
              {mode === "signup" ? "Create Account" : "Welcome Back"}
            </h1>
            {workspaceDestination && mode === "signin" && (
              <p className="login-subtext mb-2">
                {workspaceDestination === "#dashboards" ? "Sign in to open your dashboards." : "Sign in to open your workspace."}
              </p>
            )}
            <p className="login-subtext">
              {mode === "signup" ? (
                <>
                  Already have an account?{" "}
                  <button
                    type="button"
                    onClick={() => switchMode("signin")}
                    className="login-link-btn"
                  >
                    Sign in
                  </button>
                </>
              ) : (
                <>
                  Don&apos;t have an account?{" "}
                  <button
                    type="button"
                    onClick={() => switchMode("signup")}
                    className="login-link-btn"
                  >
                    Sign up
                  </button>
                </>
              )}
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name field (if signing up) */}
            {mode === "signup" && (
              <div>
                <label className="login-label" htmlFor="login-name">
                  Full Name
                </label>
                <input
                  type="text"
                  id="login-name"
                  name="name"
                  value={formData.name}
                  onChange={handleInputChange}
                  placeholder="Your Name"
                  className="login-input"
                  required
                />
              </div>
            )}

            {/* Email */}
            <div>
              <label className="login-label" htmlFor="login-email">
                Email Address
              </label>
              <input
                type="email"
                id="login-email"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                placeholder="name@company.com"
                autoComplete="email"
                className="login-input"
                required
              />
            </div>

            {/* Password */}
            <div>
              <label className="login-label" htmlFor="login-password">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  id="login-password"
                  name="password"
                  value={formData.password}
                  onChange={handleInputChange}
                  placeholder="••••••••"
                  autoComplete={mode === "signup" ? "new-password" : "current-password"}
                  minLength={mode === "signup" ? 8 : 1}
                  className="login-input pr-12"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="login-eye-btn"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <EyeOff className="w-5 h-5" />
                  ) : (
                    <Eye className="w-5 h-5" />
                  )}
                </button>
              </div>
            </div>

            {/* Remember Me + Forgot Password */}
            <div className="flex items-center justify-between pt-1">
              <label className="login-remember">
                <input
                  type="checkbox"
                  name="rememberMe"
                  checked={formData.rememberMe}
                  onChange={handleInputChange}
                />
                <span>Remember me</span>
              </label>
              <button
                type="button"
                onClick={handleForgotPassword}
                className="login-link-btn"
              >
                Forgot password?
              </button>
            </div>

            {/* Error or Notice messages */}
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-xs font-mono">
                {error}
              </div>
            )}
            {notice && (
              <div className="p-3 bg-blue-50 border border-blue-200 text-blue-700 rounded-xl text-xs font-mono">
                {notice}
              </div>
            )}

            {/* Submit Button - HIGH VISIBILITY JET BLACK BUTTON */}
            <div className="pt-2">
              <button
                type="submit"
                disabled={busy}
                className="login-submit-btn"
              >
                {busy ? "Authenticating…" : mode === "signup" ? "Create Account" : "Sign In"}
              </button>
            </div>

          </form>
        </div>
      </div>
    </div>
  );
}
