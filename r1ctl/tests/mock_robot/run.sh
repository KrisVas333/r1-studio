#!/bin/bash
# $1 = signal name, $2 = seconds into the move, $3 = second signal after N s (optional)
export PATH=$PATH
cd /tmp/mb || exit 1
L=/tmp/mock.log; rm -f $L
./mock_robot lo $L 0.3 & M=$!
sleep 1.5
CSV=/r1/r1ctl/library/arm/m_cheer.csv
/r1/r1ctl/bin/r1_arm lo traj $CSV 1.0 > /tmp/arm.out 2>&1 & A=$!
T0=$(date +%s.%N)
sleep $2
kill -$1 $A
[ -n "$3" ] && { sleep $3; kill -$1 $A; }
wait $A; RC=$?
T1=$(date +%s.%N)
sleep 0.4; kill $M 2>/dev/null
echo "signal=$1 at=$2 exit=$RC took=$(python3 -c "print(round($T1-$T0,2))") out=$(tr '\n' ' ' < /tmp/arm.out)"
python3 - <<'PY'
rows=[l.split() for l in open('/tmp/mock.log') if len(l.split())==3]
r=[(float(a),int(b),float(c)) for a,b,c in rows]
print(' first', r[0], ' peak q', max(x[2] for x in r) if r else None, min(x[2] for x in r))
print(' last with mode100', [x for x in r if x[1]==100][-1])
tail=[x for x in r if x[1]<100]
print(' ramp rows', len(tail), 'ends', tail[-1] if tail else None)
sp=[abs(b[2]-a[2])/max(1e-3,b[0]-a[0]) for a,b in zip(r,r[1:])]
print(' top speed seen %.2f rad/s'%max(sp))
PY
