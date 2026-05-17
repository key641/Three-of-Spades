export function FeedbackPanel() {
  return (
    <section className="panel full-width">
      <h2>行程反馈</h2>
      <div className="feedback-grid">
        <label>路线合理性<input type="range" min="1" max="5" defaultValue="4" /></label>
        <label>餐厅满意度<input type="range" min="1" max="5" defaultValue="4" /></label>
        <label>排队控制<input type="range" min="1" max="5" defaultValue="4" /></label>
        <label>预算满意度<input type="range" min="1" max="5" defaultValue="4" /></label>
      </div>
    </section>
  );
}

