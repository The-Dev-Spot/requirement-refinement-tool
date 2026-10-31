# UX, UI and accessibility reference

**Read:** user-facing web/app/game UI, dashboards, forms, onboarding, task flows, navigation, errors and status changes. Do not require UI-specific checks for a backend-only story. **DoR:** D1/D3/D4/D5/D10.

## Sources and applicability

- [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) — stable, testable success criteria. **AA is a proposed baseline only if the project's product/accessibility policy adopts it**; never assert automatic legal conformance.
- [WCAG Understanding documents](https://www.w3.org/WAI/WCAG22/understanding/) — nonnormative explanations and implementation choices.
- [Android accessibility](https://developer.android.com/guide/topics/ui/accessibility/) — roles/labels, contrast, touch targets, traversal, assistive technology and testing for native Android apps.
- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/design-principles/) — platform UX conventions, user control, privacy, recovery and accessibility for Apple products.
- [Nielsen Norman Group: 10 usability heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/) — **heuristics, not compliance controls**; assist evaluating clarity, visibility, error prevention and recovery.
- [NN/g: usability research](https://www.nngroup.com/articles/usability-101-introduction-to-usability/) — iterative testing with real users.

## Story-specific challenges

1. **Task and journey:** What is the user's goal, entry route, success state, and safe way to back out? Is the primary action visually and semantically clear?
2. **States:** Define loading, empty, offline, failure, partial success, duplicate submit, validation error, long wait, and recovery only where they can happen. Don't invent a page for a system without a UI.
3. **Accessibility:** For interactive UI check name/role/value, keyboard/focus flow, touch target, non-color-only state, contrast, text resizing and screen-reader announcements as applicable to the platform and adopted policy.
4. **Consistency:** What existing design system/component pattern, navigation convention, terminology and responsive breakpoint does the product already use? Ask where no authoritative design exists.
5. **Control and feedback:** Does the UI tell the user when a long-running action is in progress, failed, interrupted or needs approval? Can destructive changes be confirmed or reversed?
6. **Internationalization:** If product supports multiple languages, currencies, times or units, what actual locale/format/RTL rules are required? Don't assume every application is global.
7. **Validation:** Which real task can someone complete on keyboard/touch/assistive tech and across target screen/device sizes? Automated checks alone cannot certify usability.

## Example outcome criteria (illustrative)

- When a submission fails, the same form preserves entered data, provides a programmatically associated error and offers a safe retry.
- Focus remains visible and moves to the new dialog when opened, then returns to the initiating control when dismissed.
- An asynchronous workflow announces a meaningful progress/complete/blocked state; state does not depend on color alone.
- In an actual accessibility review, identify the **specific WCAG success criterion and applicable conformance target**; don't write `WCAG compliant` as one unchecked acceptance criterion.

## Game UI vs app UI

Use these principles for game HUDs, pause/restart menus, motion/audio indicators, input remapping and legibility where relevant. Visual polish and playability also require representative playtesting; do not prescribe full game-engine device testing for a server-side defect.

**Deliverable split:** build-relevant visual states and accessibility behavior go in the short story; research, screenshots, alternatives, usability study notes and evidence remain in run evidence. Preserve the 3–6/max-8 acceptance budget.
