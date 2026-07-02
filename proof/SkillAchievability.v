(* ============================================================= *)
(*  SkillAchievability.v                                          *)
(*  Mechanized soundness core for the Skill Achievability        *)
(*  Compiler (Layer A).                                          *)
(*                                                               *)
(*  What is proved here (Coq 8.18, no external libraries):       *)
(*                                                               *)
(*   T0  reach_trans   : reachability is transitive.             *)
(*   L1  reach_abs     : a sound abstraction transports          *)
(*                       concrete reachability to the abstract   *)
(*                       transition system.                      *)
(*   T1  refutation_sound :                                      *)
(*         if the ABSTRACT system cannot reach any goal state,   *)
(*         then NO concrete run reaches the goal.                *)
(*         (=> the checker never emits a false "IMPOSSIBLE".)    *)
(*   T2  tolerance_sound :                                       *)
(*         refutation under a COARSER over-approximation         *)
(*         transfers to every finer system. (=> making the       *)
(*         abstraction more tolerant keeps refutation sound.)    *)
(*   T3  cap_monotone  :                                         *)
(*         adding capabilities can only enlarge the reachable    *)
(*         set; it never turns ACHIEVABLE into IMPOSSIBLE.       *)
(*                                                               *)
(*   FlightInstance : a concrete non-vacuity model proving that  *)
(*         the missing-email-capability spec (the hallucinated-  *)
(*         planning failure) is genuinely refuted -- there is    *)
(*         provably no run reaching  booked /\ confirmation.     *)
(* ============================================================= *)

(* ---------- Generic reachability (reflexive-transitive closure) ---------- *)

Section Reachability.
  Context {St : Type}.
  Variable step : St -> St -> Prop.

  Inductive reach (s : St) : St -> Prop :=
  | reach_refl : reach s s
  | reach_step : forall u v, reach s u -> step u v -> reach s v.

  Lemma reach_one : forall s v, step s v -> reach s v.
  Proof. intros s v H. eapply reach_step. apply reach_refl. exact H. Qed.

  Lemma reach_trans : forall s u v, reach s u -> reach u v -> reach s v.
  Proof.
    intros s u v Hsu Huv. induction Huv as [| x y Hux IH Hxy].
    - exact Hsu.
    - eapply reach_step. apply IH. exact Hxy.
  Qed.
End Reachability.

(* ---------- Monotonicity of reachability in the step relation ---------- *)

Lemma reach_mono {St : Type} (step1 step2 : St -> St -> Prop) :
  (forall x y, step1 x y -> step2 x y) ->
  forall s w, reach step1 s w -> reach step2 s w.
Proof.
  intros Hsub s w H. induction H as [| u v Hsu IH Huv].
  - apply reach_refl.
  - eapply reach_step. apply IH. apply Hsub. exact Huv.
Qed.

(* ============================================================= *)
(*  T1  Refutation soundness via a sound abstraction             *)
(* ============================================================= *)

Section Soundness.
  Context {W A : Type}.
  Variable cstep : W -> W -> Prop.   (* concrete transition system *)
  Variable astep : A -> A -> Prop.   (* abstract system the checker explores *)
  Variable abs   : W -> A.           (* abstraction function *)
  Variable cgoal : W -> Prop.        (* concrete goal *)
  Variable agoal : A -> Prop.        (* abstract goal *)

  (* The two obligations that make the abstraction SOUND. *)
  Hypothesis step_sim : forall w w', cstep w w' -> astep (abs w) (abs w').
  Hypothesis goal_sim : forall w, cgoal w -> agoal (abs w).

  (* L1: abstraction transports reachability. *)
  Lemma reach_abs :
    forall s0 w, reach cstep s0 w -> reach astep (abs s0) (abs w).
  Proof.
    intros s0 w H. induction H as [| u v Hsu IH Huv].
    - apply reach_refl.
    - eapply reach_step. apply IH. apply step_sim. exact Huv.
  Qed.

  (* T1: if the abstract system has no reachable goal, neither does the
         concrete one.  This is THE guarantee: a "REFUTED" verdict from
         the checker is never wrong. *)
  Theorem refutation_sound :
    forall s0,
      (~ exists a, reach astep (abs s0) a /\ agoal a) ->
      (~ exists w, reach cstep s0 w /\ cgoal w).
  Proof.
    intros s0 Hno [w [Hreach Hgoal]].
    apply Hno. exists (abs w). split.
    - apply reach_abs. exact Hreach.
    - apply goal_sim. exact Hgoal.
  Qed.
End Soundness.

(* ============================================================= *)
(*  T2  Tolerance soundness                                       *)
(*  A coarser (more permissive) over-approximation that still     *)
(*  cannot reach the goal refutes every finer system.            *)
(* ============================================================= *)

Section Tolerance.
  Context {A : Type}.
  Variables fine coarse : A -> A -> Prop.
  Hypothesis over : forall x y, fine x y -> coarse x y.
  Variable agoal : A -> Prop.

  Theorem tolerance_sound :
    forall s0,
      (~ exists a, reach coarse s0 a /\ agoal a) ->
      (~ exists a, reach fine s0 a /\ agoal a).
  Proof.
    intros s0 Hno [a [Hreach Hgoal]].
    apply Hno. exists a. split.
    - apply (reach_mono fine coarse over). exact Hreach.
    - exact Hgoal.
  Qed.
End Tolerance.

(* ============================================================= *)
(*  T3  Capability monotonicity                                   *)
(*  Enlarging the available steps (granting more tools) can only  *)
(*  grow the reachable set: more capabilities never make an       *)
(*  achievable goal impossible.                                   *)
(* ============================================================= *)

Section CapabilityMonotone.
  Context {A : Type}.
  Variables stepLo stepHi : A -> A -> Prop.   (* fewer / more capabilities *)
  Hypothesis grant : forall x y, stepLo x y -> stepHi x y.
  Variable agoal : A -> Prop.

  Theorem cap_monotone :
    forall s0 a, reach stepLo s0 a -> agoal a ->
                 exists a', reach stepHi s0 a' /\ agoal a'.
  Proof.
    intros s0 a Hreach Hgoal. exists a. split.
    - apply (reach_mono stepLo stepHi grant). exact Hreach.
    - exact Hgoal.
  Qed.
End CapabilityMonotone.

(* ============================================================= *)
(*  Concrete non-vacuity instance: the hallucinated-planning      *)
(*  failure mechanically refuted.                                 *)
(*                                                               *)
(*  Goal: booked /\ confirmation_sent.                           *)
(*  Capabilities present: search, filter, book.                  *)
(*  Capability ABSENT: send_email (so confirmation_sent can       *)
(*  never become true).                                          *)
(*                                                               *)
(*  We prove directly that no reachable state satisfies the      *)
(*  goal -- i.e. the checker's REFUTED verdict is correct here.   *)
(* ============================================================= *)

Module FlightInstance.

  Record World := mk {
    searched : bool;
    filtered : bool;
    booked   : bool;
    conf     : bool   (* confirmation_sent *)
  }.

  (* Concrete steps for the THREE capabilities the agent actually has.
     Crucially, none of them touches [conf], because there is no
     send_email capability in scope. *)
  Inductive cstep : World -> World -> Prop :=
  | do_search : forall w,
      cstep w (mk true (filtered w) (booked w) (conf w))
  | do_filter : forall w,
      searched w = true ->
      cstep w (mk (searched w) true (booked w) (conf w))
  | do_book : forall w,
      filtered w = true ->
      cstep w (mk (searched w) (filtered w) true (conf w)).

  Definition s0 : World := mk false false false false.
  Definition cgoal (w : World) : Prop := booked w = true /\ conf w = true.

  (* Invariant: every concrete step preserves [conf]. *)
  Lemma step_preserves_conf : forall w w', cstep w w' -> conf w' = conf w.
  Proof. intros w w' H. destruct H; simpl; reflexivity. Qed.

  (* Therefore confirmation is never sent on any run from s0. *)
  Lemma conf_stays_false : forall w, reach cstep s0 w -> conf w = false.
  Proof.
    intros w H. induction H as [| u v Hsu IH Huv].
    - reflexivity.
    - rewrite (step_preserves_conf u v Huv). exact IH.
  Qed.

  (* Refutation: the goal is unreachable. The verdict "IMPOSSIBLE" is sound. *)
  Theorem flight_refuted : ~ exists w, reach cstep s0 w /\ cgoal w.
  Proof.
    intros [w [Hreach [_ Hconf]]].
    rewrite (conf_stays_false w Hreach) in Hconf. discriminate Hconf.
  Qed.

  (* Sanity: the agent CAN still get a booking -- the spec is not vacuously
     stuck; only the confirmation half is impossible. This shows the
     refutation is about the missing capability, not a dead protocol. *)
  Theorem booking_reachable :
    exists w, reach cstep s0 w /\ booked w = true.
  Proof.
    exists (mk true true true false). split.
    - eapply reach_step.
      eapply reach_step.
      eapply reach_step.
      apply reach_refl.
      (* search: s0 -> mk true false false false *)
      apply (do_search s0).
      (* filter: searched=true *)
      apply (do_filter (mk true false false false)). reflexivity.
      (* book: filtered=true *)
      apply (do_book (mk true true false false)). reflexivity.
    - reflexivity.
  Qed.

End FlightInstance.
