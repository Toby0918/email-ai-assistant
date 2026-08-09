"""Latent fixed transaction vocabulary; it grants no production reachability."""


TRANSACTION_ACKNOWLEDGEMENT = "ACKNOWLEDGE_R2_TRANSACTION_ACTION"
TRANSACTION_VERBS = {
    "execute": "execute",
    "resume": "resume",
    "rollback": "rollback",
}
