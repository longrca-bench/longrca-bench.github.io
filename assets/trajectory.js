"use strict";

(() => {
  const root = document.querySelector("#trajectory-example");
  if (!root) return;

  const svgNamespace = "http://www.w3.org/2000/svg";
  const map = root.querySelector("[data-trajectory-map]");
  const range = root.querySelector("[data-trace-range]");
  const playButton = root.querySelector("[data-trace-play]");
  const progress = root.querySelector("[data-trace-progress]");
  const errorMessage = root.querySelector("[data-trajectory-error]");
  let payload = null;
  let selectedStep = 0;
  let playTimer = null;

  const makeElement = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  };

  const makeSvg = (tag, attributes = {}) => {
    const element = document.createElementNS(svgNamespace, tag);
    Object.entries(attributes).forEach(([key, value]) =>
      element.setAttribute(key, String(value)),
    );
    return element;
  };

  const actorLabel = (actorId) =>
    payload.actors.find((actor) => actor.id === actorId)?.label || actorId;

  const phaseLabel = (phaseId) =>
    payload.phases.find((phase) => phase.id === phaseId)?.label || phaseId;

  const stopPlayback = () => {
    if (playTimer !== null) window.clearInterval(playTimer);
    playTimer = null;
    playButton.textContent = "▶";
    playButton.setAttribute("aria-label", "Play trajectory");
  };

  const updateSelectedNode = () => {
    map.querySelectorAll("[data-trace-step]").forEach((node) => {
      node.classList.toggle(
        "selected-event",
        Number(node.dataset.traceStep) === selectedStep,
      );
    });
  };

  const setSelectedStep = (step) => {
    if (!payload) return;
    selectedStep = Math.max(0, Math.min(payload.events.length - 1, Number(step)));
    const event = payload.events[selectedStep];
    range.value = String(selectedStep);
    progress.textContent = `${selectedStep} / ${payload.events.length - 1}`;
    root.querySelector("[data-trace-actor]").textContent = actorLabel(event.actor);
    root.querySelector("[data-trace-phase]").textContent = phaseLabel(event.phase);
    root.querySelector("[data-trace-title]").textContent = event.title;
    root.querySelector("[data-trace-detail]").textContent = event.detail;
    root.querySelector("[data-trace-candidates]").textContent =
      event.state.candidates.toLocaleString("en-US");
    root.querySelector("[data-trace-checks]").textContent =
      event.state.checks.toLocaleString("en-US");
    root.querySelector("[data-trace-notes]").textContent =
      event.state.notes.toLocaleString("en-US");
    updateSelectedNode();
  };

  const drawMap = () => {
    const width = 1160;
    const labelWidth = 126;
    const right = 24;
    const top = 60;
    const rowHeight = 43;
    const bottom = 28;
    const height = top + payload.actors.length * rowHeight + bottom;
    const eventX = (index) =>
      labelWidth +
      (index / (payload.events.length - 1)) * (width - labelWidth - right);
    const actorIndex = Object.fromEntries(
      payload.actors.map((actor, index) => [actor.id, index]),
    );
    const eventY = (actorId) => top + actorIndex[actorId] * rowHeight + rowHeight / 2;
    const failureSteps = new Set(payload.failure_path.map((item) => item.step));

    map.replaceChildren();
    map.setAttribute("viewBox", `0 0 ${width} ${height}`);
    const title = makeSvg("title");
    title.textContent = "Seventy-seven-step multi-agent execution trace";
    const description = makeSvg("desc");
    description.textContent =
      "Events move through eight agent lanes. Failure-relevant events are highlighted at steps 24, 51, 69, and 74.";
    map.append(title, description);

    payload.phases.forEach((phase, index) => {
      const startX = eventX(phase.start);
      const endX = eventX(phase.end);
      map.appendChild(
        makeSvg("rect", {
          x: startX - 5,
          y: 28,
          width: Math.max(12, endX - startX + 10),
          height: height - 42,
          class: `trace-phase-band phase-band-${index % 2}`,
        }),
      );
      const label = makeSvg("text", {
        x: (startX + endX) / 2,
        y: 18,
        "text-anchor": "middle",
        class: "trace-phase-label",
      });
      label.textContent = phase.label;
      map.appendChild(label);
    });

    payload.actors.forEach((actor) => {
      const y = eventY(actor.id);
      map.appendChild(
        makeSvg("line", {
          x1: labelWidth,
          y1: y,
          x2: width - right,
          y2: y,
          class: "trace-lane-line",
        }),
      );
      const label = makeSvg("text", {
        x: labelWidth - 12,
        y: y + 4,
        "text-anchor": "end",
        class: "trace-actor-label",
      });
      label.textContent = actor.label;
      map.appendChild(label);
    });

    const route = payload.events
      .map((event, index) =>
        `${index === 0 ? "M" : "L"} ${eventX(event.index)} ${eventY(event.actor)}`,
      )
      .join(" ");
    map.appendChild(makeSvg("path", { d: route, class: "trace-route-line" }));

    payload.events.forEach((event) => {
      const group = makeSvg("g", {
        class: "trace-event",
        tabindex: "0",
        role: "button",
        "data-trace-step": event.index,
        "aria-label": `Step ${event.index}: ${actorLabel(event.actor)}, ${event.title}`,
      });
      const isFailureStep = failureSteps.has(event.index);
      const circle = makeSvg("circle", {
        cx: eventX(event.index),
        cy: eventY(event.actor),
        r: event.tone === "error" || isFailureStep ? 6 : 3.3,
        class:
          event.tone === "error"
            ? "trace-node error-node"
            : isFailureStep
              ? "trace-node failure-node"
              : event.tone === "final"
                ? "trace-node final-node"
                : "trace-node normal-node",
      });
      const nodeTitle = makeSvg("title");
      nodeTitle.textContent = `Step ${event.index} · ${actorLabel(event.actor)} · ${event.title}`;
      group.append(circle, nodeTitle);
      const select = () => {
        stopPlayback();
        setSelectedStep(event.index);
      };
      group.addEventListener("click", select);
      group.addEventListener("keydown", (keyboardEvent) => {
        if (keyboardEvent.key === "Enter" || keyboardEvent.key === " ") {
          keyboardEvent.preventDefault();
          select();
        }
      });
      map.appendChild(group);
    });
  };

  const renderFailurePath = () => {
    const container = root.querySelector("[data-failure-path]");
    container.replaceChildren();
    payload.failure_path.forEach((item, index) => {
      const card = makeElement("button", "failure-step-card");
      card.type = "button";
      card.setAttribute("aria-label", `Open step ${item.step}: ${item.label}`);
      card.append(
        makeElement("span", "failure-step-number", `Step ${item.step}`),
        makeElement("strong", "", item.label),
        makeElement("span", "failure-step-detail", item.detail),
      );
      card.addEventListener("click", () => {
        activateView("map");
        setSelectedStep(item.step);
      });
      container.appendChild(card);
      if (index < payload.failure_path.length - 1) {
        container.appendChild(makeElement("span", "failure-path-arrow", "→"));
      }
    });
  };

  const renderFinalFailure = () => {
    root.querySelector("[data-manager-requirement]").textContent =
      payload.final_failure.manager_requirement;
    root.querySelector("[data-observed-failure]").textContent =
      payload.final_failure.observed_output;
    root.querySelector("[data-failure-explanation]").textContent =
      payload.final_failure.explanation;
  };

  const activateView = (viewName) => {
    root.querySelectorAll("[data-trace-tab]").forEach((button) => {
      const active = button.dataset.traceTab === viewName;
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
    });
    root.querySelectorAll("[data-trace-view]").forEach((view) => {
      view.hidden = view.dataset.traceView !== viewName;
    });
  };

  root.querySelectorAll("[data-trace-tab]").forEach((button, index, buttons) => {
    button.addEventListener("click", () => {
      stopPlayback();
      activateView(button.dataset.traceTab);
    });
    button.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      event.preventDefault();
      const direction = event.key === 'ArrowRight' ? 1 : -1;
      const nextIndex = (index + direction + buttons.length) % buttons.length;
      buttons[nextIndex].focus();
      buttons[nextIndex].click();
    });
  });

  root.querySelector("[data-trace-prev]").addEventListener("click", () => {
    stopPlayback();
    setSelectedStep(selectedStep - 1);
  });
  root.querySelector("[data-trace-next]").addEventListener("click", () => {
    stopPlayback();
    setSelectedStep(selectedStep + 1);
  });
  range.addEventListener("input", (event) => {
    stopPlayback();
    setSelectedStep(event.target.value);
  });
  playButton.addEventListener("click", () => {
    if (!payload) return;
    if (playTimer !== null) {
      stopPlayback();
      return;
    }
    if (selectedStep >= 76) setSelectedStep(0);
    playButton.textContent = "Ⅱ";
    playButton.setAttribute("aria-label", "Pause trajectory");
    const interval = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? 1200
      : 650;
    playTimer = window.setInterval(() => {
      if (selectedStep >= 76) {
        stopPlayback();
        return;
      }
      setSelectedStep(selectedStep + 1);
    }, interval);
  });

  const loadExample = async () => {
    try {
      const response = await fetch("data/example_trajectory.json");
      if (!response.ok) throw new Error("Example trajectory request failed");
      payload = await response.json();
      drawMap();
      renderFailurePath();
      renderFinalFailure();
      setSelectedStep(0);
    } catch (error) {
      errorMessage.hidden = false;
      root.classList.add("trajectory-error");
      console.error(error);
    }
  };

  loadExample();
})();
