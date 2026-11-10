const TAG = "aquarium-feeding-planner-card";
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"};
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ESCAPES[char]);
const formatGrams = (value) => `${Number(value).toFixed(2)} g`;

class AquariumFeedingPlannerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; color: var(--primary-text-color, #142c30); }
        ha-card { overflow: hidden; }
        h2, h3, p { margin: 0; }
        h2 { font-size: 1.25rem; }
        h3 { font-size: 1rem; }
        header { padding: 18px 18px 14px; border-bottom: 1px solid var(--divider-color, #d5e1df); }
        .eyebrow { color: var(--secondary-text-color, #476366); font-size: .78rem; margin-bottom: 4px; }
        .top { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
        .top select { max-width: 100%; }
        .weeks { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 15rem), 1fr)); gap: 14px; padding: 14px; }
        .week-heading { display: flex; align-items: center; justify-content: space-between; gap: 6px; padding: 0 3px 8px; }
        .badge { color: var(--secondary-text-color, #476366); font-size: .75rem; font-weight: 600; }
        .days { display: grid; gap: 7px; }
        .day { display: block; width: 100%; padding: 9px 10px; color: inherit; text-align: left;
          font: inherit; border: 1px solid var(--divider-color, #d5e1df); border-radius: 10px;
          background: var(--card-background-color, #fff); cursor: pointer; }
        .day:disabled { cursor: default; }
        .day:not(:disabled):hover, .day:focus-visible, .day[aria-current] { border-color: var(--primary-color, #147c76); }
        .day-title { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-weight: 650; }
        .meals { display: block; padding-top: 4px; }
        .meal { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 8px; line-height: 1.35; padding: 2px 0; font-size: .84rem; }
        .meal span:first-child, .note { overflow-wrap: anywhere; }
        .amount { white-space: nowrap; font-variant-numeric: tabular-nums; }
        .note, .empty { color: var(--secondary-text-color, #476366); font-size: .8rem; }
        .note { display: block; }
        .placeholder { padding: 16px 18px; color: var(--secondary-text-color, #476366); }
        button:focus-visible, select:focus-visible, input:focus-visible { outline: 2px solid var(--primary-color, #147c76); outline-offset: 2px; }
        dialog { color: inherit; background: var(--card-background-color, #fff);
          border: 1px solid var(--divider-color, #d5e1df); border-radius: 14px;
          width: min(35rem, calc(100vw - 24px)); box-sizing: border-box;
          max-height: calc(100dvh - 24px); padding: 0; }
        dialog::backdrop { background: #0008; }
        form { padding: 16px; }
        .intro { margin: 4px 0 12px; color: var(--secondary-text-color, #476366); }
        fieldset { min-width: 0; border: 1px solid var(--divider-color, #d5e1df); border-radius: 9px; margin: 0 0 9px; padding: 9px; }
        legend { font-weight: 600; }
        .fields { display: grid; grid-template-columns: minmax(0, 1fr) minmax(5rem, 7rem); gap: 8px; }
        .fields label { display: grid; gap: 3px; min-width: 0; font-size: .81rem; }
        .fields .wide { grid-column: 1 / -1; }
        select, input { min-height: 34px; color: inherit; background: var(--card-background-color, #fff);
          border: 1px solid var(--divider-color, #d5e1df); border-radius: 6px; padding: 4px 7px; box-sizing: border-box; font: inherit; }
        .fields select, .fields input { width: 100%; }
        .actions { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
        .action { cursor: pointer; font: inherit; color: inherit; background: transparent; padding: 7px 10px;
          border: 1px solid var(--divider-color, #d5e1df); border-radius: 7px; }
        .action.primary { color: var(--text-primary-color, #fff); background: var(--primary-color, #147c76); border-color: transparent; }
        .action:disabled { cursor: wait; opacity: .65; }
        .remove { margin-top: 7px; padding: 4px 7px; }
        [role="alert"] { color: var(--error-color, #a52b32); }
        [role="alert"]:empty { display: none; }
      </style>
      <ha-card><div id="view"></div></ha-card>
      <dialog aria-labelledby="edit-title"><form>
        <h2 id="edit-title"></h2>
        <p class="intro">Weights are dry grams. A 0 g portion is paused.</p>
        <div id="rows"></div>
        <p role="alert"></p>
        <div class="actions">
          <button class="action" type="button" data-add>Add food</button>
          <div>
            <button class="action" type="button" data-cancel>Cancel</button>
            <button class="action primary" type="submit">Save day</button>
          </div>
        </div>
      </form></dialog>`;
    this._view = this.shadowRoot.getElementById("view");
    this._dialog = this.shadowRoot.querySelector("dialog");
    this._rows = this.shadowRoot.getElementById("rows");
    this._error = this._dialog.querySelector('[role="alert"]');
    this._view.addEventListener("change", (event) => {
      if (event.target.matches("[data-tank]")) {
        this._selected = event.target.value;
        this._render();
      }
    });
    this._view.addEventListener("click", (event) => {
      const day = event.target.closest("button[data-week]");
      if (day) this._editDay(day.dataset.week, Number(day.dataset.day));
    });
    this._dialog.addEventListener("click", (event) => {
      if (event.target.matches("[data-add]")) this._addRow().querySelector("select").focus();
      if (event.target.matches("[data-remove]")) {
        event.target.closest("fieldset").remove();
        this._numberRows();
      }
      if (event.target.matches("[data-cancel]")) this._dialog.close();
    });
    this._dialog.addEventListener("cancel", (event) => {
      if (this._saving) event.preventDefault();
    });
    this._dialog.addEventListener("submit", (event) => {
      event.preventDefault();
      this._saveDay();
    });
  }

  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    if (config.entities !== undefined && !Array.isArray(config.entities)) {
      throw new Error("Set entities to a list of feeding plan sensors.");
    }
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 12;
  }

  _render() {
    if (!this._config || !this._hass) return;
    const states = this._hass.states;
    const entityIds = this._config.entities ?? Object.keys(states);
    const plans = entityIds.map((id) => states[id]).filter((state) => state?.attributes.week_schedule);
    if (!plans.some((plan) => plan.entity_id === this._selected)) this._selected = plans[0]?.entity_id;
    const tank = states[this._selected]?.attributes;
    const editable = Boolean(this._hass.user?.is_admin);
    const title = escapeHtml(this._config.title ?? "Aquarium feeding");
    let contents;
    if (!tank) {
      contents = `<header><h2>${title}</h2></header><p class="placeholder">Add a tank in Aquarium Feeding Planner to show its schedule.</p>`;
    } else {
      const label = (plan) => plan.attributes.tank_name ?? plan.attributes.friendly_name ?? plan.entity_id;
      const selector = plans.length > 1
        ? `<select aria-label="Tank" data-tank>${plans.map((plan) => `
          <option value="${escapeHtml(plan.entity_id)}" ${plan.entity_id === this._selected ? "selected" : ""}>${escapeHtml(label(plan))}</option>`).join("")}</select>`
        : `<span class="badge">${escapeHtml(label(plans[0]))}</span>`;
      const foodNames = new Map(tank.food_catalogue.map((food) => [food.id, food.name]));
      contents = `
        <header><p class="eyebrow">Feeding schedule</p><div class="top"><h2>${title}</h2>${selector}</div></header>
        <div class="weeks">${["a", "b"].map((week) => `
          <section aria-label="Week ${week.toUpperCase()}">
            <div class="week-heading"><h3>Week ${week.toUpperCase()}</h3>
              ${tank.current_week === week ? '<span class="badge">This week</span>' : ""}
            </div>
            <div class="days">${DAYS.map((day, index) => {
              const isToday = tank.current_week === week && tank.current_weekday === index;
              const meals = tank.week_schedule[week][index].filter((row) => row.grams > 0);
              return `<button class="day" type="button" data-week="${week}" data-day="${index}"
                ${isToday ? 'aria-current="date"' : ""} ${editable ? "" : "disabled"}>
                <span class="day-title">${day}${isToday ? '<span class="badge">Today</span>' : ""}</span>
                <span class="meals">${meals.length ? meals.map((row) => `
                  <span class="meal"><span>${escapeHtml([row.recipient, foodNames.get(row.food_id) ?? "Food unavailable"].filter(Boolean).join(": "))}</span>
                  <span class="amount">${formatGrams(row.grams)}</span></span>
                  ${row.note ? `<span class="note">${escapeHtml(row.note)}</span>` : ""}`).join("") : '<span class="empty">No feed scheduled</span>'}</span>
              </button>`;
            }).join("")}</div>
          </section>`).join("")}</div>`;
    }
    if (contents !== this._lastView) {
      this._view.innerHTML = contents;
      this._lastView = contents;
    }
  }

  _editDay(week, weekday) {
    const tank = this._hass.states[this._selected]?.attributes;
    if (!this._hass.user?.is_admin || !tank || this._dialog.open) return;
    this._editing = {week, weekday, entryId: tank.plan_entry_id, revision: tank.schedule_revision, foods: tank.food_catalogue};
    this.shadowRoot.getElementById("edit-title").textContent = `${DAYS[weekday]} · Week ${week.toUpperCase()}`;
    this._error.textContent = "";
    this._rows.replaceChildren();
    tank.week_schedule[week][weekday].forEach((row) => this._addRow(row));
    this._dialog.showModal();
  }

  _addRow(row = {}) {
    const fieldset = document.createElement("fieldset");
    fieldset.innerHTML = `
      <legend></legend>
      <div class="fields">
        <label>Food<select name="food_id" required>
          <option value="">Choose a food</option>
          ${this._editing.foods.map((food) => `<option value="${escapeHtml(food.id)}">${escapeHtml(food.name)}</option>`).join("")}
        </select></label>
        <label>Grams<input name="grams" type="number" required min="0" max="10" step="0.01" inputmode="decimal"></label>
        <label class="wide">Who gets this food<input name="recipient" type="text" placeholder="Optional"></label>
        <label class="wide">Serving note<input name="note" type="text" placeholder="Optional"></label>
      </div>
      <button class="action remove" type="button" data-remove>Remove food</button>`;
    for (const key of ["food_id", "grams", "recipient", "note"]) {
      fieldset.querySelector(`[name="${key}"]`).value = row[key] ?? "";
    }
    this._rows.append(fieldset);
    this._numberRows();
    return fieldset;
  }

  _numberRows() {
    [...this._rows.children].forEach((row, index) => {
      row.querySelector("legend").textContent = `Portion ${index + 1}`;
    });
  }

  async _saveDay() {
    if (this._saving) return;
    const edit = this._editing;
    const rows = [...this._rows.children].map((row) => ({
      food_id: row.querySelector('[name="food_id"]').value,
      grams: Number(row.querySelector('[name="grams"]').value),
      recipient: row.querySelector('[name="recipient"]').value,
      note: row.querySelector('[name="note"]').value,
    }));
    const controls = [...this._dialog.querySelectorAll("button, input, select")];
    controls.forEach((control) => { control.disabled = true; });
    this._saving = true;
    this._error.textContent = "";
    try {
      await this._hass.callWS({
        type: "aquarium_feeding_planner/save_day",
        entry_id: edit.entryId,
        revision: edit.revision,
        week: edit.week,
        weekday: edit.weekday,
        portions: rows,
      });
      this._dialog.close();
    } catch (error) {
      this._error.textContent = error?.message ?? "Unable to save this day. Please try again.";
    } finally {
      this._saving = false;
      controls.forEach((control) => { control.disabled = false; });
    }
  }
}

if (!customElements.get(TAG)) {
  customElements.define(TAG, AquariumFeedingPlannerCard);
  window.customCards = window.customCards ?? [];
  window.customCards.push({
    type: TAG,
    name: "Aquarium Feeding Planner",
    description: "View and edit Week A and Week B feeding schedules.",
  });
}
