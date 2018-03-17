
def get_extra_env_vars(node):
    num = node.parm("environment_kv_pairs").eval()
    result = []
    for i in range(1, num + 1):
        is_exclusive = node.parm("env_excl_%d" % i).eval()
        result.append({
            "name": node.parm("env_key_%d" % i).eval(),
            "value": node.parm("env_value_%d" % i).eval(),
            "merge_policy": ["append", "exclusive"][is_exclusive]
        })
    return result

