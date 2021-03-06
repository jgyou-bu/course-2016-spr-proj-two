import urllib.request
import json
import pymongo
import prov.model
import datetime
import uuid
from random import shuffle
from math import sqrt

# Until a library is created, we just use the script directly.
exec(open('../pymongo_dm.py').read())

# Set up the database connection.
client = pymongo.MongoClient()
repo = client.repo
repo.authenticate('loyuichi', 'loyuichi')

# Retrieve some data sets (not using the API here for the sake of simplicity).
startTime = datetime.datetime.now()

# Calculating p-value based on CS591 notes
def permute(x):
    shuffled = [xi for xi in x]
    shuffle(shuffled)
    return shuffled

def avg(x): # Average
    return sum(x)/len(x)

def stddev(x): # Standard deviation.
    m = avg(x)
    return sqrt(sum([(xi-m)**2 for xi in x])/len(x))

def cov(x, y): # Covariance.
    return sum([(xi-avg(x))*(yi-avg(y)) for (xi,yi) in zip(x,y)])/len(x)

def corr(x, y): # Correlation coefficient.
    if stddev(x)*stddev(y) != 0:
        return cov(x, y)/(stddev(x)*stddev(y))

def p(x, y):
    c0 = corr(x, y)
    corrs = []
    for k in range(0, 2000):
        y_permuted = permute(y)
        corrs.append(corr(x, y_permuted))
    return len([c for c in corrs if abs(c) > c0])/len(corrs)

# Aggregate food establishment counts by zip code
fe = repo['loyuichi.food_establishments'].aggregate([{'$group': {'_id': "$zip", 'count': { '$sum': 1 }}}])
fe_zips = repo['loyuichi.food_establishments'].distinct("zip")

# Aggregate ticket counts by zip code
tickets = repo['loyuichi.tickets'].aggregate([{'$group': {'_id': "$zip", 'count': { '$sum': 1 }}}])
tickets_zips = repo['loyuichi.tickets'].distinct("zip")

# Converting cursor objects to dictionaries
tickets_by_zip = {}
for ticket in tickets:
	tickets_by_zip.update({ticket["_id"]: ticket["count"]})

fe_by_zip = {}
for f in fe:
	fe_by_zip.update({f["_id"]: f["count"]})
print(fe_by_zip)

# Null hypothesis a) More food establishments in an area would not lead to more tickets given in an area
data = []

# Create (# of Food Establishment, # of Tickets) tuples based on zip codes for correlation analysis
if (len(fe_zips) > len(tickets_zips)):
	data = [(fe_by_zip[fe_zip], tickets_by_zip[fe_zip]) for fe_zip in fe_zips if fe_zip in tickets_zips]
else:
	data = [(fe_by_zip[tickets_zip], tickets_by_zip[tickets_zip]) for tickets_zip in tickets_zips if tickets_zip in fe_zips]

x = [xi for (xi, yi) in data]
y = [yi for (xi, yi) in data]

res = p(x, y)
print ("P-value for FE vs Tickets: " + str(res))

towed = repo['loyuichi.towed'].aggregate([{'$group': {'_id': "$zip", 'count': { '$sum': 1 }}}])
towed_zips = repo['loyuichi.towed'].distinct("zip")

towed_by_zip = {}
for t in towed:
	towed_by_zip.update({t["_id"]: t["count"]})


# Null hypothesis b) More food establishments in an area would not lead to more towings happening in an area
data = []

# Create (# of Food Establishment, # of Car Towings) tuples based on zip codes for correlation analysis
if (len(fe_zips) > len(towed_zips)):
	data = [(fe_by_zip[fe_zip], towed_by_zip[fe_zip]) for fe_zip in fe_zips if fe_zip in towed_zips]
else:
	data = [(fe_by_zip[towed_zip], towed_by_zip[towed_zip]) for towed_zip in towed_zips if towed_zip in fe_zips]

x = [xi for (xi, yi) in data]
y = [yi for (xi, yi) in data]

res = p(x, y)
print ("P-value for FE vs Towings: " + str(res))

endTime = datetime.datetime.now()

# Create the provenance document describing everything happening
# in this script. Each run of the script will generate a new
# document describing that invocation event. This information
# can then be used on subsequent runs to determine dependencies
# and "replay" everything. The old documents will also act as a
# log.
doc = prov.model.ProvDocument()
doc.add_namespace('alg', 'http://datamechanics.io/algorithm/loyuichi/') # The scripts in <folder>/<filename> format.
doc.add_namespace('dat', 'http://datamechanics.io/data/loyuichi/') # The data sets in <user>/<collection> format.
doc.add_namespace('ont', 'http://datamechanics.io/ontology#') # 'Extension', 'DataResource', 'DataSet', 'Retrieval', 'Query', or 'Computation'.
doc.add_namespace('log', 'http://datamechanics.io/log#') # The event log.
doc.add_namespace('bdp', 'https://data.cityofboston.gov/resource/')

this_script = doc.agent('alg:calc_ticket_fe_corr', {prov.model.PROV_TYPE:prov.model.PROV['SoftwareAgent'], 'ont:Extension':'py'})

food_establishments = doc.entity('dat:food_establishments', {'prov:label':'Food Establishment Permits', prov.model.PROV_TYPE:'ont:DataResource', 'ont:Extension':'json'})
towed = doc.entity('dat:towed', {'prov:label':'Towed', prov.model.PROV_TYPE:'ont:DataResource', 'ont:Extension':'json'})
tickets = doc.entity('dat:tickets', {'prov:label':'Tickets', prov.model.PROV_TYPE:'ont:DataResource', 'ont:Extension':'json'})

test_towed_food_establishments = doc.activity('log:a'+str(uuid.uuid4()), startTime, endTime, {'prov:label':'Test Towed', prov.model.PROV_TYPE:'ont:Computation'})
test_tickets_food_establishments = doc.activity('log:a'+str(uuid.uuid4()), startTime, endTime, {'prov:label':'Test Tickets', prov.model.PROV_TYPE:'ont:Computation'})

doc.wasAssociatedWith(test_tickets_food_establishments, this_script)
doc.wasAssociatedWith(test_towed_food_establishments, this_script)

doc.used(test_towed_food_establishments, food_establishments, startTime)
doc.used(test_tickets_food_establishments, food_establishments, startTime)
doc.used(test_towed_food_establishments, towed, startTime)
doc.used(test_tickets_food_establishments, tickets, startTime)

#repo.record(doc.serialize()) # Record the provenance document.
#print(json.dumps(json.loads(doc.serialize()), indent=4))
#open('plan.json','w').write(json.dumps(json.loads(doc.serialize()), indent=4))
print(doc.get_provn())
repo.logout()

## eof