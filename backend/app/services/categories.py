CATEGORY_GUIDANCE={
 "Pothole":{"department":"Roads Department","questions":["Approximate width or depth","Is traffic being obstructed?"],"safety":"Avoid standing in the carriageway while taking photos."},
 "Garbage accumulation":{"department":"Solid Waste Management","questions":["How long has waste remained?","Any hazardous or medical waste?"],"safety":"Do not touch unknown or sharp waste."},
 "Water leakage":{"department":"Chennai Metro Water","questions":["Is water actively flowing?","Is drinking-water supply affected?"],"safety":"Keep away from electrical equipment near water."},
 "Sewage overflow":{"department":"Chennai Metro Water","questions":["Is sewage entering homes or roads?","Any strong health risk nearby?"],"safety":"Avoid direct contact and keep children away."},
 "Broken streetlight":{"department":"Electrical Department","questions":["Pole or landmark identifier","Is wiring exposed?"],"safety":"Never touch exposed cables or damaged poles."},
 "Open drain":{"department":"Storm Water Drains","questions":["Approximate opening size","Is there a missing cover?"],"safety":"Maintain distance from the drain edge."},
 "Fallen tree":{"department":"Parks Department","questions":["Is the road fully blocked?","Are power lines involved?"],"safety":"Stay clear if cables or unstable branches are visible."},
}
def guidance(category:str):return CATEGORY_GUIDANCE.get(category,{"department":"Greater Chennai Corporation","questions":["Add a nearby landmark","Describe the public impact"],"safety":"Keep a safe distance while documenting the issue."})
