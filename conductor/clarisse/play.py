from conductor.native.lib.data_block import ConductorDataBlock

db = ConductorDataBlock(product="clarisse", force=True)

print  db.projects()

