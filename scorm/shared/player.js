/*
 * Minimal single-SCO player shared by the VIDI SI awareness modules (SCORM 1.2).
 *
 * The page is a list of <section class="slide"> elements. A slide may carry a
 * data-gate ("video" | "hotspots" | "scenarios" | "quiz") that keeps "Suivant"
 * disabled until the learner has done the activity once.
 *
 * LMS reporting:
 *   cmi.core.lesson_status  incomplete → passed | failed (quiz vs data-mastery)
 *   cmi.core.score.*        quiz score in %
 *   cmi.suspend_data        JSON bookmark (Frappe LMS only persists this field,
 *                           so the position lives here rather than in lesson_location)
 *   cmi.interactions.n.*    one entry per quiz question
 * Runs standalone too (no LMS found → nothing is reported).
 */
(function () {
  "use strict";

  // ------------------------------------------------------------------ SCORM 1.2 API

  var Scorm = (function () {
    var api = null;
    var start = Date.now();
    var finished = false;

    function lookup(win) {
      for (var i = 0; win && i < 10; i++) {
        try {
          if (win.API) return win.API;
        } catch (e) {
          return null; // cross-origin parent
        }
        if (win.parent === win) break;
        win = win.parent;
      }
      return null;
    }

    function sessionTime() {
      var s = Math.round((Date.now() - start) / 1000);
      var h = Math.floor(s / 3600);
      var m = Math.floor((s % 3600) / 60);
      var pad = function (n, w) { n = String(n); while (n.length < w) n = "0" + n; return n; };
      return pad(h, 4) + ":" + pad(m, 2) + ":" + pad(s % 60, 2);
    }

    return {
      init: function () {
        api = lookup(window) || (window.opener ? lookup(window.opener) : null);
        if (!api) {
          console.info("[scorm] Aucun LMS détecté : mode autonome, rien n'est enregistré.");
          return false;
        }
        api.LMSInitialize("");
        return true;
      },
      get: function (key) { return api ? String(api.LMSGetValue(key) || "") : ""; },
      set: function (key, value) { if (api) api.LMSSetValue(key, String(value)); },
      commit: function () { if (api) api.LMSCommit(""); },
      finish: function (exit) {
        if (!api || finished) return;
        finished = true;
        api.LMSSetValue("cmi.core.session_time", sessionTime());
        api.LMSSetValue("cmi.core.exit", exit);
        api.LMSCommit("");
        api.LMSFinish("");
      }
    };
  })();

  // ------------------------------------------------------------------ state

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  var slides = $$("main > .slide");
  var mastery = parseInt(document.body.getAttribute("data-mastery") || "80", 10);
  var prevBtn = $("#prev");
  var nextBtn = $("#next");
  var hint = $(".navbar .hint");

  // slide: current index, done: indexes of completed gated slides, score/passed: last quiz result
  var state = { slide: 0, done: {}, score: null, passed: false };

  function save() {
    Scorm.set("cmi.suspend_data", JSON.stringify(state));
    Scorm.commit();
  }

  function restore() {
    var raw = Scorm.get("cmi.suspend_data");
    if (!raw) return;
    try {
      var saved = JSON.parse(raw);
      if (saved && typeof saved.slide === "number") state = Object.assign(state, saved);
    } catch (e) { /* corrupt bookmark: start over */ }
    if (state.slide >= slides.length) state.slide = 0;
  }

  // ------------------------------------------------------------------ navigation

  var GATE_HINTS = {
    video: "Regardez la vidéo jusqu'au bout pour continuer.",
    hotspots: "Trouvez tous les indices pour continuer.",
    scenarios: "Trouvez la bonne réponse à chaque situation pour continuer.",
    quiz: "Répondez à toutes les questions puis validez."
  };

  function isLocked(i) {
    var gate = slides[i].getAttribute("data-gate");
    return !!gate && !state.done[i];
  }

  function refreshNav() {
    var i = state.slide;
    prevBtn.disabled = i === 0;
    var last = i === slides.length - 1;
    nextBtn.disabled = last || isLocked(i);
    nextBtn.textContent = last ? "Terminé" : "Suivant →";
    hint.textContent = isLocked(i) ? GATE_HINTS[slides[i].getAttribute("data-gate")] : "";
    $(".topbar .counter").textContent = (i + 1) + " / " + slides.length;
    $(".progress > div").style.width = ((i + 1) / slides.length) * 100 + "%";
  }

  function show(i) {
    var leaving = slides[state.slide];
    $$("video", leaving).forEach(function (v) { v.pause(); });
    slides.forEach(function (s, k) { s.classList.toggle("active", k === i); });
    state.slide = i;
    if (slides[i].hasAttribute("data-results")) renderResults();
    refreshNav();
    $("main").scrollTop = 0;
    var h = $("h1, h2", slides[i]);
    if (h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); }
    save();
  }

  function complete(slide) {
    var i = slides.indexOf(slide);
    if (state.done[i]) return;
    state.done[i] = true;
    refreshNav();
    save();
  }

  prevBtn.addEventListener("click", function () { if (state.slide > 0) show(state.slide - 1); });
  nextBtn.addEventListener("click", function () {
    if (!nextBtn.disabled) show(state.slide + 1);
  });
  document.addEventListener("keydown", function (e) {
    if (/INPUT|TEXTAREA|VIDEO/.test(document.activeElement.tagName)) return;
    if (e.key === "ArrowRight" && !nextBtn.disabled) show(state.slide + 1);
    if (e.key === "ArrowLeft" && !prevBtn.disabled) show(state.slide - 1);
  });

  // ------------------------------------------------------------------ video gate

  $$("[data-gate=video]").forEach(function (slide) {
    var video = $("video", slide);
    var mark = function () { complete(slide); };
    video.addEventListener("ended", mark);
    video.addEventListener("timeupdate", function () {
      if (video.duration && video.currentTime / video.duration > 0.95) mark();
    });
  });

  // ------------------------------------------------------------------ hotspots

  $$("[data-hotspots]").forEach(function (box) {
    var slide = box.closest(".slide");
    var spots = $$(".hotspot", box);
    var list = $(".found-list", slide);
    var counter = $(".found-count", slide);
    var found = 0;
    var update = function () { if (counter) counter.textContent = found + " / " + spots.length; };
    update();
    spots.forEach(function (spot) {
      spot.setAttribute("tabindex", "0");
      spot.setAttribute("role", "button");
      var hit = function () {
        if (spot.classList.contains("found")) return;
        spot.classList.add("found");
        found++;
        var li = document.createElement("li");
        li.innerHTML = spot.getAttribute("data-label");
        list.appendChild(li);
        update();
        if (found === spots.length) complete(slide);
      };
      spot.addEventListener("click", hit);
      spot.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); hit(); }
      });
    });
  });

  // ------------------------------------------------------------------ scenarios

  $$("[data-gate=scenarios]").forEach(function (slide) {
    var scenarios = $$(".scenario", slide);
    scenarios.forEach(function (sc) {
      var fb = $(".feedback", sc);
      $$(".options .btn", sc).forEach(function (btn) {
        btn.addEventListener("click", function () {
          var right = btn.hasAttribute("data-correct");
          btn.classList.add(right ? "right" : "wrong");
          fb.className = "feedback show " + (right ? "good" : "bad");
          fb.innerHTML = (right ? "<strong>Bon réflexe.</strong> " : "<strong>Pas tout à fait.</strong> ") +
            btn.getAttribute("data-feedback");
          if (right) {
            sc.classList.add("solved");
            $$(".options .btn", sc).forEach(function (b) { b.disabled = true; });
            if (scenarios.every(function (s) { return s.classList.contains("solved"); })) complete(slide);
          }
        });
      });
    });
  });

  // ------------------------------------------------------------------ password meter (local only)

  $$("[data-widget=password-meter]").forEach(function (box) {
    var input = $("input", box);
    var bar = $(".meter > div", box);
    var label = $(".meter-label", box);
    var tips = $(".meter-tips", box);
    var COMMON = ["password", "motdepasse", "azerty", "qwerty", "123456", "soleil", "bonjour", "admin", "welcome", "loulou", "marseille", "paris"];
    var LEVELS = [
      [0, "#c62828", "Très faible"],
      [40, "#e65100", "Faible"],
      [60, "#f9a825", "Moyen"],
      [80, "#2e7d32", "Robuste"],
      [100, "#1b5e20", "Très robuste"]
    ];

    function evaluate(pw) {
      var pool = 0;
      if (/[a-z]/.test(pw)) pool += 26;
      if (/[A-Z]/.test(pw)) pool += 26;
      if (/[0-9]/.test(pw)) pool += 10;
      if (/[^a-zA-Z0-9]/.test(pw)) pool += 33;
      var bits = pw.length * Math.log2(pool || 1);
      var advice = [];
      var lower = pw.toLowerCase();
      if (COMMON.some(function (w) { return lower.indexOf(w) !== -1; })) { bits = Math.min(bits, 20); advice.push("Contient un mot très courant, testé en premier par les attaquants."); }
      if (/(.)\1\1/.test(pw)) { bits -= 10; advice.push("Évitez les caractères répétés (aaa, 111…)."); }
      if (/(19|20)\d\d/.test(pw)) { bits -= 8; advice.push("Une année (naissance, embauche…) se devine facilement."); }
      if (pw.length < 12) advice.push("Visez au moins 12 caractères — 16 ou plus avec une phrase de passe.");
      if (pool < 60 && pw.length < 20) advice.push("Mélangez majuscules, minuscules, chiffres et caractères spéciaux… ou allongez.");
      return { bits: Math.max(0, bits), advice: advice };
    }

    input.addEventListener("input", function () {
      var pw = input.value;
      if (!pw) { bar.style.width = "0"; label.textContent = "—"; tips.innerHTML = ""; return; }
      var r = evaluate(pw);
      var pct = Math.min(100, Math.round(r.bits / 100 * 100));
      var lvl = LEVELS[0];
      LEVELS.forEach(function (l) { if (pct >= l[0]) lvl = l; });
      bar.style.width = Math.max(pct, 4) + "%";
      bar.style.background = lvl[1];
      label.textContent = lvl[2] + " (≈ " + Math.round(r.bits) + " bits)";
      tips.innerHTML = r.advice.map(function (a) { return "<li>" + a + "</li>"; }).join("");
    });
  });

  // ------------------------------------------------------------------ quiz

  var quizSlide = $("[data-gate=quiz]");
  var questions = quizSlide ? $$(".q", quizSlide) : [];

  questions.forEach(function (q, n) {
    var multi = q.getAttribute("data-answer").indexOf(",") !== -1;
    $$("input", q).forEach(function (input) {
      input.type = multi ? "checkbox" : "radio";
      input.name = "q" + n;
    });
    var kind = document.createElement("span");
    kind.className = "kind";
    kind.textContent = multi ? "Plusieurs réponses possibles" : "Une seule réponse";
    $("legend", q).insertAdjacentElement("afterend", kind);
  });

  function selected(q) {
    return $$("input:checked", q).map(function (i) { return i.value; }).sort().join(",");
  }

  function resetQuiz() {
    questions.forEach(function (q) {
      q.classList.remove("graded");
      $$("input", q).forEach(function (i) { i.checked = false; i.disabled = false; });
      $$(".choice", q).forEach(function (c) { c.classList.remove("correct", "incorrect"); });
    });
    $("#quiz-submit").disabled = false;
    delete state.done[slides.indexOf(quizSlide)];
    if (!state.passed) Scorm.set("cmi.core.lesson_status", "incomplete");
  }

  if (quizSlide) {
    $("#quiz-submit").addEventListener("click", function () {
      var missing = questions.filter(function (q) { return !selected(q); });
      if (missing.length) {
        hint.textContent = missing.length === 1 ? "Il reste 1 question sans réponse." : "Il reste " + missing.length + " questions sans réponse.";
        missing[0].scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
      var correct = 0;
      questions.forEach(function (q, n) {
        var expected = q.getAttribute("data-answer").split(",").sort().join(",");
        var given = selected(q);
        var ok = given === expected;
        if (ok) correct++;
        q.classList.add("graded");
        $$("input", q).forEach(function (input) {
          input.disabled = true;
          var shouldBe = expected.split(",").indexOf(input.value) !== -1;
          var label = input.closest(".choice");
          if (shouldBe) label.classList.add("correct");
          else if (input.checked) label.classList.add("incorrect");
        });
        var p = "cmi.interactions." + n + ".";
        Scorm.set(p + "id", q.id || "q" + (n + 1));
        Scorm.set(p + "type", "choice");
        Scorm.set(p + "correct_responses.0.pattern", expected);
        Scorm.set(p + "student_response", given);
        Scorm.set(p + "result", ok ? "correct" : "wrong");
      });
      $("#quiz-submit").disabled = true;
      var score = Math.round((correct / questions.length) * 100);
      state.score = score;
      state.passed = state.passed || score >= mastery;
      Scorm.set("cmi.core.score.min", 0);
      Scorm.set("cmi.core.score.max", 100);
      Scorm.set("cmi.core.score.raw", score);
      Scorm.set("cmi.core.lesson_status", score >= mastery ? "passed" : "failed");
      state.done[slides.indexOf(quizSlide)] = true;
      state.lastCorrect = correct;
      save();
      show(slides.indexOf(quizSlide) + 1);
    });
  }

  function renderResults() {
    var box = $("[data-results] .result");
    if (!box) return;
    if (state.score === null) {
      box.className = "result";
      box.innerHTML = "<p>Terminez le quiz pour voir votre résultat.</p>";
      return;
    }
    var pass = state.score >= mastery;
    box.className = "result " + (pass ? "pass" : "fail");
    var total = questions.length;
    var got = typeof state.lastCorrect === "number" ? state.lastCorrect + " / " + total + " bonnes réponses · " : "";
    box.innerHTML =
      "<div class=\"eyebrow\">" + (pass ? "Module validé" : "Module non validé") + "</div>" +
      "<div class=\"big\">" + state.score + " %</div>" +
      "<p>" + got + "seuil de réussite : " + mastery + " %</p>" +
      "<p class=\"lead\">" + (pass
        ? "Bravo ! Vous avez acquis les réflexes essentiels de ce module."
        : "Relisez les explications sous chaque question, puis retentez votre chance.") + "</p>" +
      "<div class=\"actions\">" +
      "<button class=\"btn\" type=\"button\" data-action=\"review\">Revoir mes réponses</button>" +
      "<button class=\"btn" + (pass ? "" : " primary") + "\" type=\"button\" data-action=\"retry\">Recommencer le quiz</button>" +
      "</div>";
    $("[data-action=review]", box).addEventListener("click", function () { show(slides.indexOf(quizSlide)); });
    $("[data-action=retry]", box).addEventListener("click", function () { resetQuiz(); show(slides.indexOf(quizSlide)); });
    // A reloaded page has the score but not the graded answers: review is meaningless then.
    if (!questions[0].classList.contains("graded")) $("[data-action=review]", box).remove();
  }

  // ------------------------------------------------------------------ boot

  $(".topbar .course").textContent = document.title;
  Scorm.init();
  restore();
  var status = Scorm.get("cmi.core.lesson_status");
  if (status === "passed" || status === "completed") state.passed = true;
  else Scorm.set("cmi.core.lesson_status", "incomplete");
  show(state.slide);

  var leave = function () {
    save();
    Scorm.finish(state.passed ? "" : "suspend");
  };
  window.addEventListener("pagehide", leave);
  window.addEventListener("beforeunload", leave);
})();
