import { useState, useEffect, type ChangeEvent, type FormEvent } from "react";
import { Eye, EyeOff, ArrowLeft } from "lucide-react";
import { db } from "./client";
import { useAction } from "./useAction";

interface LoginPageProps {
  initialMode?: "signin" | "signup";
  back?: () => void;
  expiredMessage?: string;
}

export function LoginPage({ initialMode = "signin", back, expiredMessage }: LoginPageProps) {
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
  }, [initialMode]);

  const navigate = (to: string) => {
    if (to === "/" || to === "") {
      if (back) back();
      else location.hash = "";
    } else if (to === "/signup" || to === "#signup") {
      setMode("signup");
      location.hash = "#signup";
      setNotice("");
    } else if (to === "/signin" || to === "#signin") {
      setMode("signin");
      location.hash = "#signin";
      setNotice("");
    } else {
      location.assign(to);
    }
  };

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
      if (!db) {
        // Without running local Supabase container, smoothly proceed to the Workspace
        navigate("/#workspace");
        return;
      }

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

  const handleOAuth = (provider: "google" | "github") => {
    void run(async () => {
      if (!db) throw Error("Start local Supabase first.");
      const { error: oauthError } = await db.auth.signInWithOAuth({
        provider,
        options: { redirectTo: location.origin },
      });
      if (oauthError) throw oauthError;
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
            onClick={() => navigate("/")}
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
            onClick={() => navigate("/")}
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
            <p className="login-subtext">
              {mode === "signup" ? (
                <>
                  Already have an account?{" "}
                  <button
                    type="button"
                    onClick={() => navigate("/signin")}
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
                    onClick={() => navigate("/signup")}
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
                <label className="login-label">
                  Full Name
                </label>
                <input
                  type="text"
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
              <label className="login-label">
                Email Address
              </label>
              <input
                type="email"
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
              <label className="login-label">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
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

            {/* Divider */}
            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-200" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="login-divider-text">OR</span>
              </div>
            </div>

            {/* Social Buttons */}
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => handleOAuth("google")}
                className="login-social-btn"
              >
                {/* Google SVG */}
                <svg className="w-4 h-4 mr-2 shrink-0" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                </svg>
                <span className="truncate">Google</span>
              </button>

              <button
                type="button"
                onClick={() => handleOAuth("github")}
                className="login-social-btn"
              >
                {/* GitHub SVG */}
                <svg className="w-4 h-4 mr-2 shrink-0" fill="#24292f" viewBox="0 0 24 24">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                </svg>
                <span className="truncate">GitHub</span>
              </button>
            </div>

            {/* Direct Workspace Preview */}
            <div className="pt-2 text-center">
              <button
                type="button"
                onClick={() => navigate("/#workspace")}
                className="login-link-btn text-xs"
              >
                Preview Workspace & post-login dashboard ↗
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
