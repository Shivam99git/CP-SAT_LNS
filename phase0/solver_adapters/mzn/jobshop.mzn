% Dynamic job shop, identical semantics to phase0/schedule_validator.py.
% Data: operations 1..n with machine, duration, start bounds [lb,ub]
% (commitments have lb=ub); job precedence pairs; outages; optional kept
% machine-order arcs (restricted neighbourhoods) and a makespan cutoff.
include "disjunctive.mzn";
int: n;
int: n_mach;
int: H;
array[1..n] of int: mach;
array[1..n] of int: dur;
array[1..n] of int: lb;
array[1..n] of int: ub;
int: n_prec;
array[1..n_prec] of int: pa;
array[1..n_prec] of int: pb;
int: n_last;
array[1..n_last] of int: last;
int: n_out;
array[1..n_out] of int: om;
array[1..n_out] of int: os;
array[1..n_out] of int: oe;
int: n_arc;
array[1..n_arc] of int: au;
array[1..n_arc] of int: av;
int: cutoff;       % H if none

array[1..n] of var int: s;
constraint forall(i in 1..n)(s[i] >= lb[i] /\ s[i] <= ub[i]);
constraint forall(k in 1..n_prec)(s[pb[k]] >= s[pa[k]] + dur[pa[k]]);
constraint forall(k in 1..n_arc)(s[av[k]] >= s[au[k]] + dur[au[k]]);
% unary machines: positive-duration operations plus fixed outage blocks
constraint forall(m in 1..n_mach)(
  let { set of int: O = {i | i in 1..n where mach[i] = m /\ dur[i] > 0},
        set of int: Q = {k | k in 1..n_out where om[k] = m /\ oe[k] > os[k]} } in
  if card(O) + card(Q) > 1 then
    disjunctive([s[i] | i in O] ++ [os[k] | k in Q], [dur[i] | i in O] ++ [oe[k] - os[k] | k in Q])
  else true endif);
var 0..H: cmax;
constraint forall(k in 1..n_last)(cmax >= s[last[k]] + dur[last[k]]);
constraint cmax <= cutoff;
solve minimize cmax;
output ["{\"cmax\": \(cmax), \"s\": \(s)}"];
