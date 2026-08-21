"""factsheet_core.py - the vehicle's machine-readable self-description.

The subset (section 8) fixes WHICH fields are exchanged; the NUMBERS are the
agv layer's (invariant 10), so they arrive here as a config dict read from
the per-vehicle file and none is invented in code. The eight agvActions are
the machine-readable statement of exactly what actions_core implements - the
two lists are tied by a test so they cannot drift apart.
"""
import actions_core

# instant-only support for the eight (subset section 6: all instant scope;
# startCharging is also valid as a node action, declared when step 4 uses it)
_ACTION_SCOPES = {name: ["INSTANT"] for name in actions_core.SUPPORTED}


def build_factsheet(header, cfg):
    """cfg is the per-vehicle config's `factsheet:` mapping, plus map_id."""
    phys = cfg["physical"]
    msg = dict(header)
    msg.update({
        "typeSpecification": {
            "seriesName": cfg["series_name"],
            "agvKinematic": cfg["kinematic"],
            "agvClass": cfg["agv_class"],
            "maxLoadMass": cfg["max_load_mass_kg"],
            "localizationTypes": ["NATURAL"],
            "navigationTypes": ["AUTONOMOUS"],
        },
        "physicalParameters": {
            "speedMin": phys["speed_min_mps"],
            "speedMax": phys["speed_max_mps"],
            "accelerationMax": phys["accel_max_mps2"],
            "decelerationMax": phys["decel_max_mps2"],
            "heightMax": phys["height_m"],
            "width": phys["width_m"],
            "length": phys["length_m"],
        },
        "protocolLimits": {
            "maxStringLens": {},
            "maxArrayLens": {},
            "timing": {"minOrderInterval": cfg["min_order_interval_s"],
                       "minStateInterval": cfg["min_state_interval_s"]},
        },
        "protocolFeatures": {
            "optionalParameters": [
                {"parameter": "order.nodes.nodePosition", "support": "REQUIRED"},
                {"parameter": "state.agvPosition", "support": "SUPPORTED"},
                {"parameter": "state.paused", "support": "SUPPORTED"},
                {"parameter": "state.newBaseRequest", "support": "SUPPORTED"},
            ],
            "agvActions": [
                {"actionType": name, "actionScopes": _ACTION_SCOPES[name]}
                for name in actions_core.SUPPORTED],
        },
        "agvGeometry": {},
        "loadSpecification": {},
    })
    return msg
