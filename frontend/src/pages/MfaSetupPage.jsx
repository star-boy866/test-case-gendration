import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  ShieldCheck,
  QrCode,
  Copy,
  Check,
  Key,
  AlertTriangle,
  Loader2,
  ArrowRight,
  Shield,
  Download,
} from "lucide-react";
import { setupMfa, confirmMfa } from "../services/api";
import { useAuth } from "../context/AuthContext.jsx";

export default function MfaSetupPage() {
  const { refreshUser } = useAuth();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [setupData, setSetupData] = useState(null); // { secret, otpauth_url, backup_codes }
  const [code, setCode] = useState("");
  const [copiedSecret, setCopiedSecret] = useState(false);
  const [copiedCodes, setCopiedCodes] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    setupMfa()
      .then((res) => setSetupData(res.data))
      .catch((err) => {
        setError(err.response?.data?.detail || "Could not initialize MFA setup.");
      })
      .finally(() => setLoading(false));
  }, []);

  const handleCopySecret = () => {
    if (setupData?.secret) {
      navigator.clipboard.writeText(setupData.secret);
      setCopiedSecret(true);
      setTimeout(() => setCopiedSecret(false), 2000);
    }
  };

  const handleCopyBackupCodes = () => {
    if (setupData?.backup_codes) {
      navigator.clipboard.writeText(setupData.backup_codes.join("\n"));
      setCopiedCodes(true);
      setTimeout(() => setCopiedCodes(false), 2000);
    }
  };

  const handleDownloadCodes = () => {
    if (setupData?.backup_codes) {
      const blob = new Blob(
        [`HEALTHCARE TEST GEN - MFA BACKUP RECOVERY CODES\nGenerated: ${new Date().toISOString()}\n\n` + setupData.backup_codes.join("\n")],
        { type: "text/plain" }
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "mfa-recovery-codes.txt";
      a.click();
      URL.revokeObjectURL(url);
    }
  };

  const handleConfirm = async (e) => {
    e.preventDefault();
    if (code.trim().length !== 6) {
      setError("Please enter the 6-digit code from your authenticator app.");
      return;
    }

    setConfirming(true);
    setError(null);

    try {
      await confirmMfa({ code: code.trim() });
      setSuccess(true);
      await refreshUser();
      setTimeout(() => {
        navigate("/cognos", { replace: true });
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.detail || "Invalid 6-digit verification code. Please check time sync.");
    } finally {
      setConfirming(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-900 text-white">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  const qrImageUrl = setupData?.otpauth_url
    ? `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(setupData.otpauth_url)}`
    : null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 px-4 py-10 text-slate-100">
      <div className="w-full max-w-xl rounded-2xl border border-slate-700/70 bg-slate-800/90 p-8 shadow-2xl backdrop-blur-md">
        
        {/* Header */}
        <div className="mb-6 flex items-center gap-3 border-b border-slate-700/80 pb-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-500/20 text-blue-400 border border-blue-500/30">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">Setup Multi-Factor Authentication</h1>
            <p className="text-xs text-slate-400">
              Mandatory for Administrative Accounts • RFC 6238 TOTP Standard
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-5 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3.5 text-xs text-rose-300">
            {error}
          </div>
        )}

        {success ? (
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-6 text-center text-emerald-300 space-y-2">
            <ShieldCheck className="mx-auto h-12 w-12 text-emerald-400" />
            <h3 className="text-base font-bold text-white">MFA Successfully Activated!</h3>
            <p className="text-xs text-slate-300">Your account is now secured. Redirecting to workspace…</p>
          </div>
        ) : (
          <div className="space-y-6">
            
            {/* Step 1: Scan QR or Enter Secret */}
            <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-4 space-y-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-blue-400">
                Step 1: Link Authenticator App
              </span>
              <p className="text-xs text-slate-300 leading-relaxed">
                Scan this QR code with Google Authenticator, Microsoft Authenticator, 1Password, or Bitwarden.
              </p>

              <div className="flex flex-col sm:flex-row items-center gap-5 pt-2">
                {qrImageUrl && (
                  <div className="rounded-xl bg-white p-2.5 shadow-md shrink-0">
                    <img src={qrImageUrl} alt="TOTP QR Code" className="h-36 w-36" />
                  </div>
                )}
                <div className="space-y-2 w-full">
                  <span className="block text-[11px] font-medium text-slate-400">
                    Cannot scan QR? Enter secret key manually:
                  </span>
                  <div className="flex items-center gap-2 rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-xs font-mono text-emerald-400">
                    <span className="truncate">{setupData?.secret}</span>
                    <button
                      type="button"
                      onClick={handleCopySecret}
                      className="ml-auto text-slate-400 hover:text-white"
                      title="Copy secret key"
                    >
                      {copiedSecret ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                    </button>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Account name: <span className="text-slate-300">Cognos Test Gen</span>
                  </p>
                </div>
              </div>
            </div>

            {/* Step 2: Backup Recovery Codes */}
            {setupData?.backup_codes && (
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-amber-400">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    <span className="text-xs font-bold uppercase tracking-wider">
                      Step 2: Save Emergency Recovery Codes
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={handleCopyBackupCodes}
                      className="flex items-center gap-1 rounded bg-slate-800/80 px-2 py-1 text-[11px] text-slate-300 hover:text-white border border-slate-600"
                    >
                      {copiedCodes ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                      <span>{copiedCodes ? "Copied" : "Copy"}</span>
                    </button>
                    <button
                      type="button"
                      onClick={handleDownloadCodes}
                      className="flex items-center gap-1 rounded bg-slate-800/80 px-2 py-1 text-[11px] text-slate-300 hover:text-white border border-slate-600"
                    >
                      <Download className="h-3 w-3" />
                      <span>Download</span>
                    </button>
                  </div>
                </div>
                <p className="text-[11px] text-slate-300">
                  Store these recovery codes securely. Each code is single-use and allows login if your device is lost.
                </p>
                <div className="grid grid-cols-4 gap-1.5 pt-1">
                  {setupData.backup_codes.map((codeStr, idx) => (
                    <span
                      key={idx}
                      className="rounded bg-slate-900/90 py-1 text-center font-mono text-xs text-amber-200 border border-slate-700"
                    >
                      {codeStr}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Step 3: Enter 6-digit Code */}
            <form onSubmit={handleConfirm} className="space-y-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-blue-400">
                Step 3: Verify & Activate
              </span>
              <div>
                <label className="mb-1 block text-xs text-slate-300">
                  Enter the 6-digit verification code from your authenticator app:
                </label>
                <div className="flex gap-3">
                  <input
                    type="text"
                    maxLength={6}
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                    placeholder="123456"
                    className="w-48 rounded-xl border border-slate-600 bg-slate-900 px-4 py-2.5 text-center font-mono text-lg font-bold tracking-widest text-white placeholder-slate-600 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                    required
                  />
                  <button
                    type="submit"
                    disabled={confirming || code.length !== 6}
                    className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-700 px-4 py-2.5 text-sm font-semibold text-white shadow-md hover:from-blue-500 hover:to-blue-600 disabled:opacity-50"
                  >
                    {confirming ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <>
                        <span>Activate 2FA</span>
                        <ArrowRight className="h-4 w-4" />
                      </>
                    )}
                  </button>
                </div>
                <div className="pt-2 text-center">
                  <button
                    type="button"
                    onClick={() => navigate("/cognos")}
                    className="text-xs text-slate-400 hover:text-slate-200 underline transition-colors"
                  >
                    Skip for now & continue to Application →
                  </button>
                </div>
              </div>
            </form>

          </div>
        )}

      </div>
    </div>
  );
}
