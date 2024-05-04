def prove_valid_block(self, _block):
    if _block.prev_hash != self.last_block().hash or (
    not _block.calculate_block_hash.startswith('0' * _block.difficulty)):
        return False
    return True

def prove_valid_chain(self, another_chain):
    return True ### for implement

def broadcast_block():
    None

def get_block():
    None

### API to interact with disk data
### so python file is only to interact with disk data
### should not store blockchain in the python running