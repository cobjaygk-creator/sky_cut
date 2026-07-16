import type { FormEvent } from "react";
import type { View } from "../types";

export function AuthPanel({
  view,
  email,
  password,
  message,
  isLoading,
  onEmailChange,
  onPasswordChange,
  onSubmit,
  onToggleView,
}: {
  view: View;
  email: string;
  password: string;
  message: string;
  isLoading: boolean;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onToggleView: () => void;
}) {
  return (
    <section className="auth-panel" aria-label={view === "login" ? "로그인" : "회원가입"}>
      <p className="create-kicker">{view === "login" ? "로그인" : "회원가입"}</p>
      <h2>{view === "login" ? "스튜디오 입장" : "무료로 시작하기"}</h2>
      <p className="auth-lead">
        {view === "login"
          ? "계정으로 들어가 쇼츠 제작을 이어가세요."
          : "이메일만으로 시작하고, 블로그·유튜브·MP4로 쇼츠를 만들 수 있어요."}
      </p>
      <form className="auth-form" onSubmit={onSubmit}>
        <label>
          이메일
          <input type="email" value={email} onChange={(event) => onEmailChange(event.target.value)} autoComplete="email" required />
        </label>
        <label>
          비밀번호
          <input
            type="password"
            value={password}
            onChange={(event) => onPasswordChange(event.target.value)}
            autoComplete={view === "login" ? "current-password" : "new-password"}
            minLength={view === "register" ? 8 : 1}
            required
          />
        </label>
        {message ? <p className="form-message">{message}</p> : null}
        <button className="cta-button" type="submit" disabled={isLoading}>
          {isLoading ? "잠시만요…" : view === "login" ? "로그인" : "계정 만들기"}
        </button>
      </form>
      <button className="link-button" type="button" onClick={onToggleView}>
        {view === "login" ? "계정이 없나요? 회원가입" : "이미 계정이 있어요"}
      </button>
    </section>
  );
}
