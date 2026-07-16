import type { Plan, Usage } from "../types";

export function UsagePanel({ usage, plans }: { usage: Usage | null; plans: Plan[] }) {
  return (
    <section className="usage-panel" aria-label="사용량 및 요금제">
      <div className="usage-summary">
        <div>
          <span>현재 요금제</span>
          <strong>{usage ? usage.plan_name : "불러오는 중"}</strong>
        </div>
        <div>
          <span>이번 달 사용량</span>
          <strong>{usage ? `${usage.monthly_usage}/${usage.usage_limit}` : "-"}</strong>
        </div>
        <div>
          <span>최대 영상 길이</span>
          <strong>{usage ? `${usage.max_video_minutes}분` : "-"}</strong>
        </div>
      </div>
      <div className="plans-grid">
        {plans.map((plan) => (
          <article className={`plan-tile ${usage?.plan === plan.id ? "active-plan" : ""}`} key={plan.id}>
            <div>
              <strong>{plan.name}</strong>
              <span>월 {plan.monthly_video_limit}개</span>
            </div>
            <p>영상당 최대 {plan.max_video_minutes}분</p>
          </article>
        ))}
      </div>
    </section>
  );
}
