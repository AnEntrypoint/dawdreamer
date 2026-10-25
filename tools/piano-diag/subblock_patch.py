import sys

HEAD_OLD = "refineFreq(x, w, coarseFreq) = refinedFreq\nwith {\n"
HEAD_NEW = "refineFreq(x, w, coarseFreq) = refinedFreq, refinedLag, delta, delta2, L0, Lraw\nwith {\n"
TAIL_OLD = "detectedFreq(x) = heldFreq, confident\n"
TAIL_NEW = r'''detectedFreq(x) = heldFreq, confident, coarseFreq, refinedNow, refinedLagNow, deltaNow, delta2Now, L0Now, LrawNow, takeNew, pathCode, dominant2, demoteNow
with {
    xh = xHp(x);
    w = tableStep ~ _;
    coarseFreq = pickFundamental(xh);
    demoteNow = demoteTest(xh, w, coarseFreq);
    demoteDuty = demoteNow : *(1.0-demotePole) : + ~ *(demotePole);
    promotion = subharmonicPromote(xh, w, coarseFreq, demoteNow);
    dominant3 = promotion : (!, !, _, !);
    dominant2 = promotion : (!, !, !, _);
    finalConfidence = promotion : (!, _, !, !);
    refinedH = refineFreq(xh, w, coarseFreq * 0.5);
    refined1 = refineFreq(xh, w, coarseFreq);
    refined2 = refineFreq(xh, w, coarseFreq * 2.0);
    refined3 = refineFreq(xh, w, coarseFreq * 3.0);
    lanes = refinedH, refined1, refined2, refined3;
    pickPath(a, b, c, d) = ba.if(dominant3, d, ba.if(dominant2, c, ba.if(demoteNow, a, b)));
    refinedNow = lanes : (_,!,!,!,!,!, _,!,!,!,!,!, _,!,!,!,!,!, _,!,!,!,!,!) : pickPath;
    refinedLagNow = lanes : (!,_,!,!,!,!, !,_,!,!,!,!, !,_,!,!,!,!, !,_,!,!,!,!) : pickPath;
    deltaNow = lanes : (!,!,_,!,!,!, !,!,_,!,!,!, !,!,_,!,!,!, !,!,_,!,!,!) : pickPath;
    delta2Now = lanes : (!,!,!,_,!,!, !,!,!,_,!,!, !,!,!,_,!,!, !,!,!,_,!,!) : pickPath;
    L0Now = lanes : (!,!,!,!,_,!, !,!,!,!,_,!, !,!,!,!,_,!, !,!,!,!,_,!) : pickPath;
    LrawNow = lanes : (!,!,!,!,!,_, !,!,!,!,!,_, !,!,!,!,!,_, !,!,!,!,!,_) : pickPath;
    pathCode = ba.if(dominant3, 3.0, ba.if(dominant2, 2.0, ba.if(demoteNow, 0.5, 1.0)));
    coarsePrev = coarseFreq : mem;
    coarseMove = abs(coarseFreq - coarsePrev) > max(0.5, octaveSemitone * coarsePrev);
    coarseStill = 1.0 - coarseMove;
    countStable(prev) = min(confirmSamples, prev + 1.0);
    stableRun = ba.if(coarseStill, countStable, 0.0) ~ _;
    takeNew = (stableRun >= confirmSamples) & ((demoteNow > 0.5) | (demoteDuty <= 0.5));
    holdStep(prev) = ba.if(takeNew, refinedNow, prev);
    heldFreq = holdStep ~ _;
    confident = finalConfidence >= corrThresh;
};

onsetHoldMs = 35.0;
onsetHoldSamples = int(onsetHoldMs * 0.001 * ma.SR);

energyReady(x) = ready
with {
    envTau = 0.003;
    envPole = ba.tau2pole(envTau);
    env = x*x : *(1.0-envPole) : + ~ *(envPole);
    aboveFloor = env > 1e-6;
    countUp(prev) = min(onsetHoldSamples, prev + 1);
    holdCount = ba.if(aboveFloor, countUp, 0) ~ _;
    ready = holdCount >= onsetHoldSamples;
};

holdLastGood(freqHz, ready, confident) = out
with {
    fallingEdge = (ready:mem) * (1.0 - ready);
    accept = ready & confident;
    heldStep(prev) = ba.if(accept, freqHz, ba.if(fallingEdge > 0.5, 0.0, prev));
    out = heldStep ~ _;
};

process(sig) = holdLastGood(rawFreq, ready, confident), detected, ready
with {
    detected = detectedFreq(sig);
    rawFreqUnclamped = detected : (_, !, !, !, !, !, !, !, !, !, !, !, !);
    confident = detected : (!, _, !, !, !, !, !, !, !, !, !, !, !);
    rawFreq = rawFreqUnclamped : max(minTrackHz) : min(maxTrackHz);
    ready = energyReady(sig);
};
'''

def instrument(text):
    for old in (HEAD_OLD, TAIL_OLD):
        count = text.count(old)
        if count != 1:
            raise SystemExit("anchor matched %d times: %r" % (count, old))
    text = text.replace(HEAD_OLD, HEAD_NEW)
    return text[:text.index(TAIL_OLD)] + TAIL_NEW

if __name__ == "__main__":
    open(sys.argv[2], "w").write(instrument(open(sys.argv[1]).read()))
