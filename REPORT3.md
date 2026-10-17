# Homework 3


## Блок А

### 2.1 :

1. **kubectl get ingress -A**
![img.png](image_for_readme/ingres_kubectl.png)
2. **kubectl get pods -A**
![img.png](image_for_readme/get_pods.png)
3. MlFlow
![img.png](image_for_readme/mlflow.png)

## Блок Б

### 2.2:
1. Champion
![img.png](image_for_readme/week_champion.png)
2. Challenger
![img.png](image_for_readme/justWeek.png)
3. SOTA
![img.png](image_for_readme/BestOfTheBest.png)
MlFlow:
![img.png](image_for_readme/MlFlow2.png)
![img_1.png](image_for_readme/6.png)

**Поставил жесткий Mini_Gain, так как для замены модели требуется значительные изменения в качестве**

### 2.3:
1. До отката:
![img.png](image_for_readme/img1234124.png)
2. После отката:
![img.png](image_for_readme/12312.png)

По времени заняло около 60 секунд от клика в UI, до ответа старой версии

## Блок С

### 2.4:
1. Runner in GitHub ![img.png](image_for_readme/runner.png)
2. [ссылка на прогон](https://github.com/Stolide-anseed/Homework/actions/runs/39008442440)

### 2.5:
1. dvc push - train.csv
```
(mobile-price-service) PS C:\Users\stoli\PycharmProjects\Homework_1> uv run dvc push                              
Collecting                                                                                                                                                                            |1.00 [00:00,  383entry/s]
Pushing
1 file pushed    
```
2. dvc push - change_blue.csv
```
(mobile-price-service) PS C:\Users\stoli\PycharmProjects\Homework_1> uv run dvc push                    
Collecting                                                                                                                                                                            |2.00 [00:00,  333entry/s]
Pushing
1 file pushed   
```
3. dvc diff
```
(mobile-price-service) PS C:\Users\stoli\PycharmProjects\Homework_1> uv run dvc diff HEAD~1
Added:
    data\change_blue.csv

files summary: 1 added
```