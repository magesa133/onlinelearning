import numpy as np

lst = np.array([[[1,2,3], [2,2,3]], [[3,4,2], [5,4,3]]])

for i in lst:
    for j in i:
       for k in j:
           print(k)
           