import numpy as np
from mesh import *
from abaqus import *
from abaqusConstants import *
from caeModules import *
from regionToolset import *

nIntervals = 80
myModel = mdb.models['Model-1']
platePart = myModel.parts['plate']
myAsm = myModel.rootAssembly
plateAsm = myAsm.instances['plate']

jobName = 'het4_c'

materialName = 'DP1000'
materialFile = 'DP1000M.inp'
isMBW = 1

moveDistance = 16 *unitFactor
simTime = 0.001

supportFric = 0.20
punchFric = 0.10

varList = ('S', 'PEEQ', 'U', 'RF', 'SDV', 'STATUS') # if apply MBW, do not forget SDV


# # material params
# do not care this if use mbw input file
youngMod = 210000
poissonRatio = 0.3
density = 7.85e-9 / (unitFactor)**3
# # # Create material
myModel.Material(name = materialName)
myMaterial = myModel.materials[materialName]
myMaterial.Elastic(table=((youngMod, poissonRatio), ))
myMaterial.Density(table=((density, ), ))
# # # Section Assignment
myModel.HomogeneousSolidSection(material = materialName, name = 'Section-1', thickness = None)
platePart.SectionAssignment(sectionName = 'Section-1', region = Region(cells = platePart.cells))
# # # Define BCs
# symm BC if cut
if symmFac <= 2:
    myModel.XsymmBC(createStepName = 'Initial', name='halfSymm', 
        region=Region(faces=plateAsm.faces.getByBoundingBox(
        xMin=-w, xMax=0, yMin=-t, yMax=t, zMin=-w, zMax=w) ))
        
if symmFac <= 1:
    myModel.ZsymmBC(createStepName = 'Initial', name='quaterSymm', 
        region=Region(faces=plateAsm.faces.getByBoundingBox(
        xMin=-w, xMax=w, yMin=-t, yMax=t, zMin=-w, zMax=0) ))
# fixed BC
myModel.EncastreBC(createStepName='Initial', name='top-fix',
    region=myAsm.sets['top-fix'])
myModel.EncastreBC(createStepName='Initial', name='box-fix',
    region=myAsm.sets['bot-fix'])
# move BC
moveAmp = myModel.TabularAmplitude(name='ramp', data=((0, 0), (simTime, 1),))
myModel.ExplicitDynamicsStep(name = 'move', previous = 'Initial', timePeriod = simTime)
myModel.DisplacementBC(createStepName = 'move', name = 'move', 
    region=myAsm.sets['refPunch'], u2=moveDistance, amplitude='ramp', 
    u1=0,u3=0,ur1=0,ur2=0,ur3=0)  

# # # interaction properties
myModel.ContactProperty('punch')
if punchFric == 0:
    myModel.interactionProperties['punch'].TangentialBehavior(
        formulation=FRICTIONLESS)
else:
    myModel.interactionProperties['punch'].TangentialBehavior(
        formulation=PENALTY, fraction=0.005, maximumElasticSlip=FRACTION, 
        table=((punchFric, ), ))
# # # contact
myAsm.Surface(name='bot-nonfix-surf', 
    side1Faces=plateAsm.faces.getByBoundingCylinder(
    center1=(0,-t,0), center2=(0,0,0), radius=holderD/2.))
myAsm.Surface(name='hole-surf',
    side1Faces=plateAsm.faces.getByBoundingCylinder(
    center1=(0,t,0), center2=(0,0,0), radius=d/2.))
myAsm.SurfaceByBoolean(name='contact', surfaces=(myAsm.surfaces['bot-nonfix-surf'], myAsm.surfaces['hole-surf']),
        operation=UNION)
myAsm.Surface(name='punch-surf', 
    side1Faces=punchAsm.faces.getByBoundingCylinder(
    center1=(0,-punchH,0), center2=(0,punchH,0), radius=punchD/2.))
myModel.SurfaceToSurfaceContactExp(name='contact', createStepName='Initial',
    master=myAsm.surfaces['punch-surf'], slave=myAsm.surfaces['contact'],
    sliding=FINITE, interactionProperty='punch')
# # # rigidbody constraint
myModel.RigidBody(name='punchConstr', refPointRegion=myAsm.sets['refPunch'],
    surfaceRegion=myAsm.surfaces['punch-surf'])

    
# # # output request
myModel.FieldOutputRequest(name = 'F-Output-1', createStepName = 'move',
        region = MODEL, variables = varList, numIntervals = nIntervals)
myModel.FieldOutputRequest(name = 'ForceDispReq', createStepName = 'move', 
        region = myAsm.sets['refPunch'], variables = ('U', 'RF'), numIntervals = nIntervals)
# crete set for critical element
refNodes = plateAsm.nodes.getByBoundingSphere(center=(d/2.*np.sin(np.pi/4), t, d/2.*np.cos(np.pi/4)), radius=meshSizeLocal)
localElems = [refNodes[0].getElements()[idx].label for idx in range(0, len(refNodes[0].getElements()))]
myAsm.Set(name='LOCAL', elements=plateAsm.elements.sequenceFromLabels(localElems))
# # # create job
myAsm.regenerate()
job = mdb.Job(name=jobName, model=myModel)
job.writeInput()
if isMBW == 1:
    with open(jobName+'.inp', 'rU') as inpfile:
        lines = inpfile.read().rsplit('\n')
    with open(jobName+'.inp', 'w') as outfile:
        skiplines = 7 # the predefined material data generates 7 lines in input file
        counter = 0
        for line in lines:
            if line == '** MATERIALS':
                outfile.write('* INCLUDE, input='+materialFile+'\n')
                counter += 1
            if counter == 0 or counter > skiplines:
                outfile.write(line+'\n')
                continue
            counter += 1