
def _should_add(element, progression, max_size):
    """Should this element be added to this progression?

    Specifically, if the progression has 0 or 1 elements,
    then add it, as this starts the progression. Otherwise
    check if the gap between the element and the last in the
    progression is the same as the gap in the rest of the
    progression.

    """
    if len(progression) < 2:
        return True
    if len(progression) == max_size:
        return False
    return progression[1] - progression[0] == element - progression[-1]


def create(iterable, **kw):
    """Split a sequence of integers into arithmetic progressions.

    This is not necessarily the most compact set of
    progressions in the sequence as that would take too long
    for large sets, and be really difficult to code. This
    algorithm walks through the sorted sequence, gathers
    elements with the same gap as the previous element.

    """
    max_size = kw.get("max_size", len(iterable))
    iterable = sorted(iterable)
    
    if max_size == 1:
        return [[x] for x in iterable]

    if max_size < 1:
        max_size = len(iterable)
 
    results = [[]]

    # add a sentinel to the end - see below
    iterable.append(-1)
    p = 0
    for element in iterable:
        # if not adding to current progression, create a new progression.
        if not _should_add(element, results[p], max_size):
            lastp = p
            p += 1
            results.append([])

            # if the last progression only has 2 elements, then steal
            # the second of them to start this progression. Why? because
            # we are greedy and will have more chance of making longer
            # progressions if we dismantle progressions of length 2 and 
            # then pair up the straggling singles later.
            # Note that the sentinel added above ensures this rule also
            # works on the original last element.
            if len(results[lastp]) == 2:
                results[p].append(results[lastp][1])
                results[lastp] = results[lastp][:1]

        results[p].append(element)

    # remove the sentinel from the last progression, or remove the whole last
    # progression if it contains only the sentinel.
    if len(results[p]) == 1:
        results = results[:-1]
    else:
        results[p] = results[p][:-1]

    # Now join straggling singles into pairs if possible. Loop
    # through the singles, joining every other one to the one
    # before. In theory we could recurse here and look for
    # even longer progressions in the stragglers.
    progs, singles = [], []
    for prog in results:
        singles.append(prog[0]) if len(prog) == 1 else progs.append(prog)
    for i, s in enumerate(singles):
        if i % 2 == 0:
            progs.append([s])
        else:
            progs[-1].append(s)

        results = sorted(progs, key=lambda v: v[0])

    return results

# EXAMPLE RESULTS
#  print create([1, 10, 20, 30, 34, 35, 36, 37, 38, 40, 101, 201, 301])
#  [[1], [10, 20, 30], [34, 35, 36, 37, 38], [40], [101, 201, 301]]

#  print create([1, 2, 3, 5, 7, 8, 11, 13, 15, 17])
#  [[1, 2, 3], [5], [7], [8], [11, 13, 15, 17]]

#  print create([10, 20, 23, 5, 7, 8, 9, 11, 13, 15, 17])
#  [[5], [7, 8, 9, 10, 11], [13, 15, 17], [20], [23]]

#  print create(xrange(1, 50), 3)
#  [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12], [13, 14, 15], [16, 17, 18], [19, 20, 21], [22, 23, 24], [25, 26, 27], [28, 29, 30], [31, 32, 33], [34, 35, 36], [37, 38, 39], [40, 41, 42], [43, 44, 45], [46, 47, 48], [49]]
