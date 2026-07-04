(* ============================================================= *)
(*  DirectTyping.v                                                *)
(*                                                                 *)
(*  Mechanized metatheory for the "sessions-and-worlds" direct    *)
(*  typing discipline (T-Comm / T-Act / T-Goal): a global type is *)
(*  typed directly against a whole session configuration, with no *)
(*  local types, no projection, no merge operator, and no separate*)
(*  subtyping relation. This is the professor's proposed          *)
(*  simplification of paper Sections 4.3-4.4 and 5.2, mechanized. *)
(*                                                                 *)
(*  Scope. This targets the FINITE (non-recursive) fragment of    *)
(*  the calculus, exactly as SkillAchievability.v's FlightInstance*)
(*  is a finite instance of the general coinductive theory.       *)
(*  Recursive protocols (mu X. G) are handled the same way the    *)
(*  cited classical literature handles them (coinduction over     *)
(*  regular trees) and are future mechanization work -- see the   *)
(*  paper's Limitations. Likewise, the theorems below are stated  *)
(*  for the single "next move" that G's head construct prescribes;*)
(*  they do not claim closure under arbitrary reordering of        *)
(*  independent actions from unrelated roles (a permutation/       *)
(*  confluence lemma the classical projection-based literature      *)
(*  also needs for its own subject-reduction proofs, and which we   *)
(*  likewise leave to future work).                                  *)
(*                                                                    *)
(*  Proved here (Coq 8.18, no external libraries, axiom-free):        *)
(*                                                                      *)
(*   ctypes  G s W      : the direct judgment  G |- (s ; W)  built      *)
(*                         from T-Comm / T-Act / T-Goal.  T-Comm is      *)
(*                         generalized to fold BOTH directions of        *)
(*                         session subtyping into the rule itself         *)
(*                         (Sub-Int: the sender may commit to FEWER        *)
(*                         branches than G declares; Sub-Ext: the           *)
(*                         receiver may accept MORE) and, by requiring       *)
(*                         every offered branch's continuation to be         *)
(*                         checked against the SAME residual session,         *)
(*                         it rejects the unobserved-choice / deadlocking      *)
(*                         handoff WITHOUT ever computing a merge.              *)
(*                                                                                *)
(*                         T-Act's world/type pairing is stated in the           *)
(*                         lockstep convention used by the paper's own G-Act      *)
(*                         rule -- the unconsumed type pairs with the PRE-        *)
(*                         effect world, the residual type with the POST-        *)
(*                         effect world -- which corrects a transcription        *)
(*                         slip in the pasted proposal (there the two worlds     *)
(*                         were swapped).                                        *)
(*                                                                                 *)
(*   step               : the operational semantics (S-Comm / S-Act), typing-    *)
(*                         independent, exactly as in the paper's Section 4.2.   *)
(*                                                                                 *)
(*   type_directed_safety : a G-typed, non-terminal configuration can always      *)
(*                         take the step G's head construct prescribes, landing   *)
(*                         in a configuration typed by the residual global type.  *)
(*                         This is deadlock-freedom AND preservation, obtained    *)
(*                         directly from T-Comm/T-Act/T-Goal with no projection,  *)
(*                         no merge, and no local types -- the metatheoretic      *)
(*                         payoff the paper previously only cited (Sec 5.2),      *)
(*                         now proved for the new judgment.                       *)
(*   progress           : the deadlock-freedom half, stated on its own.           *)
(*                                                                                  *)
(*   HandoffInstance    : a concrete 2-role instance mechanizing the paper's own   *)
(*                        running example (Sec 1): the GOOD planner/worker         *)
(*                        handoff is ctypes-typed and its run reaches the goal;    *)
(*                        the BAD handoff (both roles start with an input) is      *)
(*                        stuck, hence -- by progress's contrapositive -- cannot   *)
(*                        be ctypes-typed by any non-trivial protocol at all.      *)
(* ============================================================= *)

Require Import List.
Import ListNotations.
Require Import SkillAchievability.

Section DirectTyping.
  Context {Role Cap Lab World : Type}.
  Variable role_eq_dec : forall r1 r2 : Role, {r1 = r2} + {r1 <> r2}.
  Variable eff : Cap -> World -> World -> Prop.   (* <W> a <W'> *)

  (* ---------------- processes (finite fragment: no recursion) ---------------- *)
  Inductive Proc :=
  | PEnd  : Proc
  | POut  : Role -> list (Lab * Proc) -> Proc     (* q ! {li.Pi}  *)
  | PIn   : Role -> list (Lab * Proc) -> Proc     (* p ? {li.Pi}  *)
  | PAct  : Cap  -> Proc -> Proc.                 (* a.P          *)

  (* ---------------- global types ---------------- *)
  Inductive G :=
  | GEnd  : G
  | GComm : Role -> Role -> list (Lab * G) -> G   (* p -> q : {li.Gi}  *)
  | GAct  : Cap  -> Role -> G -> G                (* a@p.G             *)
  | GGoal : (World -> Prop) -> G -> G.            (* checkmark phi . G *)

  (* ---------------- sessions: a total map from roles to processes ---------------- *)
  Definition Sess := Role -> Proc.

  Definition upd (s : Sess) (r : Role) (P : Proc) : Sess :=
    fun r' => if role_eq_dec r' r then P else s r'.

  Definition InPair {A : Type} (l : Lab) (x : A) (xs : list (Lab * A)) : Prop :=
    In (l, x) xs.

  (* "every label offered by xs is offered by ys" -- the shared shape of the
     I subseteq J side conditions and of both directions of subtyping. *)
  Definition LabSub {A B : Type} (xs : list (Lab*A)) (ys : list (Lab*B)) : Prop :=
    forall l x, InPair l x xs -> exists y, InPair l y ys.

  (* ------------------------------------------------------------- *)
  (*  Operational semantics: S-Comm / S-Act, independent of typing. *)
  (* ------------------------------------------------------------- *)
  Inductive step : (Sess * World) -> (Sess * World) -> Prop :=
  | S_Comm : forall (s : Sess) (W : World) (p q : Role) (l : Lab) (P Q : Proc) sendb recvb,
      s p = POut q sendb -> InPair l P sendb ->
      s q = PIn  p recvb -> InPair l Q recvb ->
      step (s, W) (upd (upd s p P) q Q, W)
  | S_Act  : forall (s : Sess) (W W' : World) (p : Role) (a : Cap) (P : Proc),
      s p = PAct a P -> eff a W W' ->
      step (s, W) (upd s p P, W').

  (* ------------------------------------------------------------- *)
  (*  The direct judgment  ctypes G s W,  read  "G |- (s ; W)".     *)
  (* ------------------------------------------------------------- *)
  Inductive ctypes : G -> Sess -> World -> Prop :=
  | CT_End  : forall s W,
      (forall r, s r = PEnd) ->
      ctypes GEnd s W
  | CT_Act  : forall a p Gc s W W' P,
      s p = PAct a P ->
      eff a W W' ->
      ctypes Gc (upd s p P) W' ->
      ctypes (GAct a p Gc) s W
  | CT_Goal : forall phi Gc s W,
      phi W ->
      ctypes Gc s W ->
      ctypes (GGoal phi Gc) s W
  | CT_Comm : forall p q gbranches s W sendb recvb,
      p <> q ->
      s p = POut q sendb ->
      s q = PIn  p recvb ->
      sendb <> nil ->
      LabSub sendb gbranches ->    (* Sub-Int: sender may offer fewer than G *)
      LabSub gbranches recvb ->    (* Sub-Ext: receiver may accept more than G *)
      (forall l P, InPair l P sendb ->
         exists Gc Q, InPair l Gc gbranches /\ InPair l Q recvb /\
                      ctypes Gc (upd (upd s p P) q Q) W) ->
      ctypes (GComm p q gbranches) s W.

  (* "G's remaining behaviour is only goal-checks down to end" *)
  Inductive Terminal : G -> Prop :=
  | Terminal_End  : Terminal GEnd
  | Terminal_Goal : forall phi Gc, Terminal Gc -> Terminal (GGoal phi Gc).

  (* ============================================================= *)
  (*  Type-directed safety: progress + preservation for the move    *)
  (*  G's head construct prescribes.                                 *)
  (* ============================================================= *)
  Theorem type_directed_safety :
    forall Gt s W,
      ctypes Gt s W ->
      ~ Terminal Gt ->
      exists s' W' Gt', step (s, W) (s', W') /\ ctypes Gt' s' W'.
  Proof.
    intros Gt s W H.
    induction H as [ s W Hend
                    | a p Gc s W W' P Hact Heff Hcont _
                    | phi Gc s W Hphi Hcont IH
                    | p q gbranches s W sendb recvb Hpq Hsp Hsq Hne Hsub1 Hsub2 Hcont ].
    - (* CT_End *) intro Hnt. exfalso. apply Hnt. constructor.
    - (* CT_Act *) intro Hnt.
      exists (upd s p P), W', Gc. split.
      + eapply S_Act; eauto.
      + exact Hcont.
    - (* CT_Goal *) intro Hnt.
      apply IH. intro HTGc. apply Hnt. constructor. exact HTGc.
    - (* CT_Comm *) intro Hnt.
      destruct sendb as [| [l P] rest].
      + congruence.
      + assert (HinP : InPair l P ((l, P) :: rest)) by (left; reflexivity).
        destruct (Hcont l P HinP) as [Gc [Q [HinGc [HinQ HtyC]]]].
        exists (upd (upd s p P) q Q), W, Gc. split.
        * eapply S_Comm; eauto.
        * exact HtyC.
  Qed.

  Corollary progress :
    forall Gt s W,
      ctypes Gt s W ->
      ~ Terminal Gt ->
      exists s' W', step (s, W) (s', W').
  Proof.
    intros Gt s W H Hnt.
    destruct (type_directed_safety Gt s W H Hnt) as [s' [W' [Gt' [Hstep _]]]].
    exists s', W'. exact Hstep.
  Qed.

  (* A configuration with no available step is stuck (used below for the
     deadlocking-handoff corollary). *)
  Definition Stuck (s : Sess) (W : World) : Prop :=
    ~ exists s' W', step (s, W) (s', W').

  Corollary stuck_untypeable :
    forall Gt s W,
      Stuck s W -> ~ Terminal Gt -> ~ ctypes Gt s W.
  Proof.
    intros Gt s W Hstuck Hnt Hty.
    apply Hstuck. apply (progress Gt s W Hty Hnt).
  Qed.

End DirectTyping.

(* ================================================================= *)
(*  HandoffInstance: the paper's own running example (Sec 1),         *)
(*  mechanized end to end against T-Comm / T-Act / T-Goal.            *)
(* ================================================================= *)
Module HandoffInstance.

  Inductive Role := Planner | Worker.
  Inductive Cap  := Deliver.
  Inductive Lab  := Req.
  Definition World := bool.  (* true = the deliverable is done *)

  Definition role_eq_dec : forall r1 r2 : Role, {r1 = r2} + {r1 <> r2}.
  Proof. decide equality. Defined.

  (* the only capability, unconditionally guarded, sets the world to [true] *)
  Definition eff (a : Cap) (w w' : World) : Prop := w' = true.

  Definition Done (w : World) : Prop := w = true.

  (* ---------------- the GOOD handoff: request, then deliver, then done ---------------- *)

  Definition G_good : @G Role Cap Lab World :=
    GComm Planner Worker
      [(Req, GAct Deliver Worker (GGoal Done GEnd))].

  Definition s_good : @Sess Role Cap Lab :=
    fun r => match r with
             | Planner => POut Worker [(Req, PEnd)]
             | Worker  => PIn  Planner [(Req, PAct Deliver PEnd)]
             end.

  Definition W0 : World := false.

  Lemma good_typed : ctypes role_eq_dec eff G_good s_good W0.
  Proof.
    unfold G_good, s_good.
    eapply CT_Comm.
    - discriminate.
    - reflexivity.
    - reflexivity.
    - discriminate.
    - intros l x Hin. destruct Hin as [Heq | []].
      assert (l = Req) by congruence. subst l.
      eexists. left. reflexivity.
    - intros l x Hin. destruct Hin as [Heq | []].
      assert (l = Req) by congruence. subst l.
      eexists. left. reflexivity.
    - intros l P Hin. destruct Hin as [Heq | []].
      assert (l = Req) by congruence. assert (P = PEnd) by congruence. subst l P.
      eexists (GAct Deliver Worker (GGoal Done GEnd)).
      eexists (PAct Deliver PEnd).
      repeat split.
      + left. reflexivity.
      + left. reflexivity.
      + eapply CT_Act.
        * unfold upd. destruct (role_eq_dec Worker Planner) as [E|_]; [discriminate E|].
          destruct (role_eq_dec Worker Worker) as [_|Ne]; [reflexivity | congruence].
        * reflexivity.
        * eapply CT_Goal.
          -- reflexivity.
          -- apply CT_End. intro r.
             unfold upd. destruct r.
             ++ destruct (role_eq_dec Planner Worker) as [E|_]; [discriminate E|].
                destruct (role_eq_dec Planner Planner) as [_|Ne]; [reflexivity | congruence].
             ++ destruct (role_eq_dec Worker Worker) as [_|Ne]; [reflexivity | congruence].
  Qed.

  Lemma good_runs_to_goal :
    exists sf, reach (step role_eq_dec eff) (s_good, W0) (sf, true).
  Proof.
    eexists.
    eapply reach_step.
    - eapply reach_step.
      + apply reach_refl.
      + eapply S_Comm with (p := Planner) (q := Worker) (l := Req);
          [reflexivity | left; reflexivity | reflexivity | left; reflexivity].
    - eapply S_Act with (p := Worker) (a := Deliver); [reflexivity | reflexivity].
  Qed.

  (* ---------------- the BAD handoff: both roles wait on each other ---------------- *)

  Definition s_bad : @Sess Role Cap Lab :=
    fun r => match r with
             | Planner => PIn Worker  [(Req, PEnd)]
             | Worker  => PIn Planner [(Req, PEnd)]
             end.

  Lemma bad_stuck : Stuck role_eq_dec eff s_bad W0.
  Proof.
    intros [s' [W' Hstep]].
    inversion Hstep; subst.
    - match goal with H : s_bad ?p = POut _ _ |- _ => destruct p; simpl in H; discriminate H end.
    - match goal with H : s_bad ?p = PAct _ _ |- _ => destruct p; simpl in H; discriminate H end.
  Qed.

  Corollary bad_untypeable :
    forall Gt, ~ Terminal Gt -> ~ ctypes role_eq_dec eff Gt s_bad W0.
  Proof.
    intros Gt Hnt.
    exact (stuck_untypeable role_eq_dec eff Gt s_bad W0 bad_stuck Hnt).
  Qed.

End HandoffInstance.
