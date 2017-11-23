#!/usr/bin/env python
import optparse
import sys
import models
from itertools import permutations
from collections import namedtuple

optparser = optparse.OptionParser()
optparser.add_option("-i", "--input", dest="input", default="../data/input", help="File containing sentences to translate (default=data/input)")
optparser.add_option("-t", "--translation-model", dest="tm", default="../data/tm", help="File containing translation model (default=data/tm)")
optparser.add_option("-l", "--language-model", dest="lm", default="../data/lm", help="File containing ARPA-format language model (default=data/lm)")
optparser.add_option("-n", "--num_sentences", dest="num_sents", default=sys.maxint, type="int", help="Number of sentences to decode (default=no limit)")
optparser.add_option("-k", "--translations-per-phrase", dest="k", default=1, type="int", help="Limit on number of translations to consider per phrase (default=1)")
optparser.add_option("-s", "--stack-size", dest="s", default=1, type="int", help="Maximum stack size (default=1)")
optparser.add_option("-v", "--verbose", dest="verbose", action="store_true", default=False,  help="Verbose mode (default=off)")
opts = optparser.parse_args()[0]

tm = models.TM(opts.tm, opts.k)
lm = models.LM(opts.lm)
french = [tuple(line.strip().split()) for line in open(opts.input).readlines()[:opts.num_sents]]

# tm should translate unknown words as-is with probability 1
for word in set(sum(french,())):
  if (word,) not in tm:
    tm[(word,)] = [models.phrase(word, 0.0)]

def extract_english_phrases(h, arr, english):
  if h.predecessor is None:
    return arr
  else:
    arr.append(h.phrase.english) if english else arr.append(h.f)
    return extract_english_phrases(h.predecessor, arr, english)

def extract_english(h): 
  return "" if h.predecessor is None else "%s%s " % (extract_english(h.predecessor), h.phrase.english)

def score(arr):
  logprob = 0.0
  auxArr = arr[:]
  auxArr.insert(0, lm.begin()[0])
  for i, word in enumerate(auxArr[:-1]):
    try:
      (lm_state, word_logprob) = lm.score(tuple(word.split()[-2:]), auxArr[i+1].split()[0])
      logprob += word_logprob
    except:
      logprob += -6
  return logprob

def swap(arr, s):
  best = arr[:]
  bests = s
  changed = False
  for i in range(len(arr[:-2])):
    for j in xrange(i+1, len(arr[:-1])):
      aux = arr[:]
      aux[i], aux[j] = aux[j], aux[i]
      sc = score(aux)
      if (sc > bests):
          bests = sc
          best = aux[:]
          changed = True
  return (best, bests, changed)

def improve(h):
  current  = extract_english_phrases(winner, [], True)[::-1]
  #currentF = extract_english_phrases(winner, [], False)[::-1]
  s_current = score(current)
  (current, s_current, c1) = swap(current, s_current)
  return current#, s_current

winners = []
sys.stderr.write("Decoding %s...\n" % (opts.input,))
for fphrase in french:
  theRange = len(fphrase)-5 if len(fphrase) > 5 else 1
  for iteration in range(theRange):
    starF = list(fphrase[0:iteration])
    listF = list(fphrase[iteration:iteration+5])
    restF = list(fphrase[iteration+5:len(fphrase)])
    permF = permutations(listF)
    for _,perm in enumerate(permF):
      f = tuple(starF + list(perm) + restF)
      hypothesis = namedtuple("hypothesis", "logprob, lm_state, predecessor, phrase, f")
      initial_hypothesis = hypothesis(0.0, lm.begin(), None, None, None)
      stacks = [{} for _ in f] + [{}]
      stacks[0][lm.begin()] = initial_hypothesis
      for i, stack in enumerate(stacks[:-1]):
        for h in sorted(stack.itervalues(),key=lambda h: -h.logprob)[:1000]: # prune
          for j in xrange(i+1,len(f)+1):
            if f[i:j] in tm:
              for phrase in tm[f[i:j]]:
                logprob = h.logprob + phrase.logprob
                lm_state = h.lm_state
                for word in phrase.english.split():
                  (lm_state, word_logprob) = lm.score(lm_state, word)
                  logprob += word_logprob
                logprob += lm.end(lm_state) if j == len(f) else 0.0
                new_hypothesis = hypothesis(logprob, lm_state, h, phrase, f[i:j])
                if lm_state not in stacks[j] or stacks[j][lm_state].logprob < logprob: # second case is recombination
                  stacks[j][lm_state] = new_hypothesis

  winner = max(stacks[-1].itervalues(), key=lambda h: h.logprob)
  winners.append(winner)

  realWinner = max(winners, key=lambda h: h.logprob)
  print " ".join(improve(realWinner))

  if opts.verbose:
    def extract_tm_logprob(h):
      return 0.0 if h.predecessor is None else h.phrase.logprob + extract_tm_logprob(h.predecessor)
    tm_logprob = extract_tm_logprob(winner)
    sys.stderr.write("LM = %f, TM = %f, Total = %f\n" % 
      (winner.logprob - tm_logprob, tm_logprob, winner.logprob))
