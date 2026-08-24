"use strict";

(() => {
  const root = document.querySelector("#trajectory-example");
  if (!root) return;

  const svgNamespace = "http://www.w3.org/2000/svg";
  const traceMap = root.querySelector("[data-trajectory-map]");
  const stateChart = root.querySelector("[data-state-chart]");
  const stateTooltip = root.querySelector("[data-state-tooltip]");
  const range = root.querySelector("[data-trace-range]");
  const playButton = root.querySelector("[data-trace-play]");
  const progress = root.querySelector("[data-trace-progress]");
  const errorMessage = root.querySelector("[data-trajectory-error]");
  const visibleSeries = { candidates: true, checks: true, notes: true };
  let payload = null;
  let selectedStep = 0;
  let playTimer = null;

  const kindLabels = {
    instruction: "Instruction",
    plan: "Plan",
    handoff: "Dispatch",
    thought: "Reasoning",
    tool: "Tool call",
    result: "Return",
    verify: "Verification",
    error: "Error",
    final: "Completion",
  };

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

  const appendEventShape = (group, event, x, y) => {
    const nodeClass =
      event.tone === "error" || event.kind === "error"
        ? "trace-node node-error"
        : event.kind === "tool"
          ? "trace-node node-tool"
          : event.kind === "handoff"
            ? "trace-node node-dispatch"
            : event.kind === "verify"
              ? "trace-node node-verification"
              : event.kind === "final"
                ? "trace-node node-completion"
                : "trace-node node-default";

    if (event.kind === "handoff") {
      group.appendChild(
        makeSvg("path", {
          d: `M ${x} ${y - 6} L ${x + 6} ${y + 5} L ${x - 6} ${y + 5} Z`,
          class: nodeClass,
        }),
      );
    } else if (event.kind === "verify") {
      group.appendChild(
        makeSvg("rect", {
          x: x - 4.5,
          y: y - 4.5,
          width: 9,
          height: 9,
          transform: `rotate(45 ${x} ${y})`,
          class: nodeClass,
        }),
      );
    } else if (event.kind === "tool" || event.kind === "error") {
      group.appendChild(
        makeSvg("rect", {
          x: x - 4,
          y: y - 4,
          width: 8,
          height: 8,
          class: nodeClass,
        }),
      );
    } else {
      group.appendChild(
        makeSvg("circle", {
          cx: x,
          cy: y,
          r: event.kind === "final" ? 5.5 : 3.6,
          class: nodeClass,
        }),
      );
    }
  };

  const drawMap = () => {
    const width = 1160;
    const labelWidth = 126;
    const right = 24;
    const top = 62;
    const rowHeight = 43;
    const bottom = 43;
    const height = top + payload.actors.length * rowHeight + bottom;
    const eventX = (index) =>
      labelWidth +
      (index / (payload.events.length - 1)) * (width - labelWidth - right);
    const actorIndex = Object.fromEntries(
      payload.actors.map((actor, index) => [actor.id, index]),
    );
    const eventY = (actorId) => top + actorIndex[actorId] * rowHeight + rowHeight / 2;

    traceMap.replaceChildren();
    traceMap.setAttribute("viewBox", `0 0 ${width} ${height}`);
    const title = makeSvg("title");
    title.textContent = "77-step agent message trace";
    const description = makeSvg("desc");
    description.textContent =
      "The trace moves from planning through transport, stay, food and attractions, verification, stay rework, manager approval, writer output, and run completion.";
    traceMap.append(title, description);

    payload.phases.forEach((phase, index) => {
      const startX = eventX(phase.start);
      const endX = eventX(phase.end);
      traceMap.appendChild(
        makeSvg("rect", {
          x: startX - 5,
          y: 28,
          width: Math.max(12, endX - startX + 10),
          height: height - 56,
          class: `trace-phase-band phase-band-${index % 2}`,
        }),
      );
      const label = makeSvg("text", {
        x: (startX + endX) / 2,
        y: 18,
        "text-anchor": "middle",
        class: "trace-phase-label",
      });
      label.textContent = endX - startX > 65 ? `P${index + 1} ${phase.label}` : `P${index + 1}`;
      traceMap.appendChild(label);
    });

    payload.actors.forEach((actor) => {
      const y = eventY(actor.id);
      traceMap.appendChild(
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
      traceMap.appendChild(label);
    });

    for (let index = 1; index < payload.events.length; index += 1) {
      traceMap.appendChild(
        makeSvg("line", {
          x1: eventX(index - 1),
          y1: eventY(payload.events[index - 1].actor),
          x2: eventX(index),
          y2: eventY(payload.events[index].actor),
          class: "trace-route-line",
        }),
      );
    }

    traceMap.appendChild(
      makeSvg("line", {
        x1: eventX(selectedStep),
        y1: 28,
        x2: eventX(selectedStep),
        y2: top + payload.actors.length * rowHeight,
        class: "selected-guide",
      }),
    );

    payload.events.forEach((event) => {
      const x = eventX(event.index);
      const y = eventY(event.actor);
      const group = makeSvg("g", {
        class: `trace-event${event.index === selectedStep ? " selected-event" : ""}`,
        tabindex: "0",
        role: "button",
        "data-trace-step": event.index,
        "aria-label": `Step ${event.index}: ${actorLabel(event.actor)}, ${event.title}`,
      });
      appendEventShape(group, event, x, y);
      if (event.index === selectedStep) {
        group.appendChild(
          makeSvg("circle", { cx: x, cy: y, r: 10, class: "selected-ring" }),
        );
      }
      const nodeTitle = makeSvg("title");
      nodeTitle.textContent = `Step ${event.index} · ${actorLabel(event.actor)} · ${event.title}`;
      group.appendChild(nodeTitle);
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
      traceMap.appendChild(group);
    });

    [0, 20, 40, 60, 76].forEach((value) => {
      const tick = makeSvg("text", {
        x: eventX(value),
        y: height - 17,
        "text-anchor": value === 0 ? "start" : value === 76 ? "end" : "middle",
        class: "trace-axis-label",
      });
      tick.textContent = String(value);
      traceMap.appendChild(tick);
    });
    const axisTitle = makeSvg("text", {
      x: (labelWidth + width - right) / 2,
      y: height - 2,
      "text-anchor": "middle",
      class: "trace-axis-label",
    });
    axisTitle.textContent = "Message step";
    traceMap.appendChild(axisTitle);
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
    root.querySelector("[data-trace-candidates]").textContent = event.state.candidates;
    root.querySelector("[data-trace-checks]").textContent = event.state.checks;
    root.querySelector("[data-trace-notes]").textContent = event.state.notes;
    drawMap();
  };

  const renderEventTable = () => {
    const eventTable = root.querySelector("[data-event-table]");
    eventTable.replaceChildren();
    payload.events.forEach((event) => {
      const row = document.createElement("tr");
      row.dataset.tone = event.tone;
      const number = makeElement("td", "number", event.index);
      const actor = makeElement("td", "", actorLabel(event.actor));
      const kind = makeElement("td");
      const kindBadge = makeElement(
        "span",
        "event-kind",
        kindLabels[event.kind] || event.kind,
      );
      kindBadge.dataset.kind = event.tone === "error" ? "error" : event.kind;
      kind.appendChild(kindBadge);
      const action = makeElement("td");
      const actionButton = makeElement("button", "event-action", event.title);
      actionButton.type = "button";
      actionButton.addEventListener("click", () => {
        activateView("map");
        setSelectedStep(event.index);
      });
      action.appendChild(actionButton);
      const phase = makeElement("td", "", phaseLabel(event.phase));
      row.append(number, actor, kind, action, phase);
      eventTable.appendChild(row);
    });
  };

  const drawStateChart = () => {
    const width = 760;
    const height = 340;
    const margin = { top: 18, right: 20, bottom: 48, left: 58 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const x = (value) => margin.left + (value / 76) * plotWidth;
    const y = (value) => margin.top + plotHeight - (value / 24) * plotHeight;
    const series = [
      { key: "candidates", label: "Candidates" },
      { key: "checks", label: "Check records" },
      { key: "notes", label: "Notes" },
    ];

    stateChart.replaceChildren();
    stateChart.setAttribute("viewBox", `0 0 ${width} ${height}`);
    const title = makeSvg("title");
    title.textContent = "Cumulative blackboard records";
    const description = makeSvg("desc");
    description.textContent =
      "Candidates grow from step 11 to 23 records, check records grow after step 49 to 8, and notes finish at 4.";
    stateChart.append(title, description);

    [0, 6, 12, 18, 24].forEach((value) => {
      stateChart.appendChild(
        makeSvg("line", {
          x1: margin.left,
          y1: y(value),
          x2: width - margin.right,
          y2: y(value),
          class: "state-grid-line",
        }),
      );
      const label = makeSvg("text", {
        x: margin.left - 9,
        y: y(value) + 4,
        "text-anchor": "end",
        class: "state-axis-label",
      });
      label.textContent = String(value);
      stateChart.appendChild(label);
    });

    [0, 20, 40, 60, 76].forEach((value) => {
      const label = makeSvg("text", {
        x: x(value),
        y: height - 25,
        "text-anchor": value === 0 ? "start" : value === 76 ? "end" : "middle",
        class: "state-axis-label",
      });
      label.textContent = String(value);
      stateChart.appendChild(label);
    });

    series.forEach((item) => {
      if (!visibleSeries[item.key]) return;
      let path = `M ${x(0)} ${y(payload.events[0].state[item.key])}`;
      for (let index = 1; index < payload.events.length; index += 1) {
        const previousValue = payload.events[index - 1].state[item.key];
        const currentValue = payload.events[index].state[item.key];
        path += ` L ${x(index)} ${y(previousValue)} L ${x(index)} ${y(currentValue)}`;
      }
      stateChart.appendChild(
        makeSvg("path", { d: path, class: `state-series state-series-${item.key}` }),
      );
    });

    const xTitle = makeSvg("text", {
      x: margin.left + plotWidth / 2,
      y: height - 3,
      "text-anchor": "middle",
      class: "state-axis-label",
    });
    xTitle.textContent = "Message step";
    const yTitle = makeSvg("text", {
      x: 13,
      y: margin.top + plotHeight / 2,
      transform: `rotate(-90 13 ${margin.top + plotHeight / 2})`,
      "text-anchor": "middle",
      class: "state-axis-label",
    });
    yTitle.textContent = "Cumulative records";
    stateChart.append(xTitle, yTitle);

    const hoverGuide = makeSvg("line", {
      y1: margin.top,
      y2: margin.top + plotHeight,
      class: "state-hover-guide",
      visibility: "hidden",
    });
    stateChart.appendChild(hoverGuide);
    const markers = {};
    series.forEach((item) => {
      const marker = makeSvg("circle", {
        r: 4,
        class: `state-marker state-series-${item.key}`,
        visibility: "hidden",
      });
      markers[item.key] = marker;
      stateChart.appendChild(marker);
    });

    const overlay = makeSvg("rect", {
      x: margin.left,
      y: margin.top,
      width: plotWidth,
      height: plotHeight,
      fill: "transparent",
      class: "state-hit-area",
    });
    overlay.addEventListener("pointermove", (event) => {
      const bounds = stateChart.getBoundingClientRect();
      const cursorX = ((event.clientX - bounds.left) / bounds.width) * width;
      const clampedX = Math.max(margin.left, Math.min(width - margin.right, cursorX));
      const eventIndex = Math.max(
        0,
        Math.min(76, Math.floor(((clampedX - margin.left) / plotWidth) * 76)),
      );
      hoverGuide.setAttribute("x1", clampedX);
      hoverGuide.setAttribute("x2", clampedX);
      hoverGuide.setAttribute("visibility", "visible");
      const values = [];
      series.forEach((item) => {
        const marker = markers[item.key];
        if (!visibleSeries[item.key]) {
          marker.setAttribute("visibility", "hidden");
          return;
        }
        const value = payload.events[eventIndex].state[item.key];
        marker.setAttribute("cx", clampedX);
        marker.setAttribute("cy", y(value));
        marker.setAttribute("visibility", "visible");
        values.push(`${item.label} ${value}`);
      });
      stateTooltip.textContent = `Step ${eventIndex} · ${values.join(" · ")}`;
      stateTooltip.hidden = false;
      stateTooltip.style.left = `${Math.min(72, Math.max(2, (clampedX / width) * 100))}%`;
    });
    overlay.addEventListener("pointerleave", () => {
      hoverGuide.setAttribute("visibility", "hidden");
      Object.values(markers).forEach((marker) =>
        marker.setAttribute("visibility", "hidden"),
      );
      stateTooltip.hidden = true;
    });
    stateChart.appendChild(overlay);
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
    if (payload && viewName === "map") drawMap();
    if (payload && viewName === "blackboard") drawStateChart();
  };

  root.querySelectorAll("[data-trace-tab]").forEach((button, index, buttons) => {
    button.addEventListener("click", () => {
      stopPlayback();
      activateView(button.dataset.traceTab);
    });
    button.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      event.preventDefault();
      const direction = event.key === "ArrowRight" ? 1 : -1;
      const nextIndex = (index + direction + buttons.length) % buttons.length;
      buttons[nextIndex].focus();
      buttons[nextIndex].click();
    });
  });

  root.querySelectorAll("[data-state-series]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.stateSeries;
      visibleSeries[key] = !visibleSeries[key];
      button.setAttribute("aria-pressed", String(visibleSeries[key]));
      drawStateChart();
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
      renderEventTable();
      drawStateChart();
      setSelectedStep(0);
    } catch (error) {
      errorMessage.hidden = false;
      root.classList.add("trajectory-error");
      console.error(error);
    }
  };

  loadExample();
})();
