# Ficha de los modelos

Detectores de imágenes generadas por IA. Salida: probabilidad de que la imagen sea generada (prob_ai). Entre 0.40 y 0.60 la API responde 'uncertain'.

Uso previsto: demo académica. No usar para decidir sobre personas ni como prueba de autenticidad. Solo vio fotos y generadores de CIFAKE y ArtiFact recortados a cuadrado; con otros generadores, capturas de pantalla o imágenes muy editadas puede fallar sin aviso. Varias fuentes de ArtiFact tienen licencias no comerciales.

## mlp

- Versión: `humo-artifact-mlp@2026-10-31` — archivo `mlp.onnx` (15.3 MB, sha256 `340b168b49acd3b2...`)
- Dataset: artifact (imágenes por split: {'test': 15003, 'train': 119982, 'unseen': 4000, 'val': 15004})
- Entrada: 200 x 200, JPEG calidad 90, recorte cuadrado central
- Hiperparámetros: {"hidden_dims": [512, 256, 128], "dropout": 0.3, "pool": 4, "batch_size": 128, "learning_rate": 0.001, "weight_decay": 0.0001, "epochs": 1, "label_smoothing": 0.0}
- Validación (época 1): ROC-AUC 0.5667, F1 0.5159, accuracy 0.5437
- Test: sin evaluar (correr src.training.evaluate)
- ONNX Runtime en CPU, 1 imagen: p50 0.12 ms (medido en la PC de entrenamiento; en Lambda se mide aparte)

## cnn

- Versión: `humo-artifact-cnn@2026-10-31` — archivo `cnn.onnx` (1.5 MB, sha256 `cb17cc826e6d3959...`)
- Dataset: artifact (imágenes por split: {'test': 15003, 'train': 119982, 'unseen': 4000, 'val': 15004})
- Entrada: 200 x 200, JPEG calidad 90, recorte cuadrado central
- Hiperparámetros: {"base_channels": 32, "dropout": 0.4, "batch_size": 128, "learning_rate": 0.001, "weight_decay": 0.0001, "epochs": 1, "label_smoothing": 0.0}
- Validación (época 1): ROC-AUC 0.5455, F1 0.6688, accuracy 0.5318
- Test: sin evaluar (correr src.training.evaluate)
- ONNX Runtime en CPU, 1 imagen: p50 1.18 ms (medido en la PC de entrenamiento; en Lambda se mide aparte)

## resnet18

- Versión: `humo-artifact-resnet18@2026-10-31` — archivo `resnet18.onnx` (42.7 MB, sha256 `b3dc98680d4fa18f...`)
- Dataset: artifact (imágenes por split: {'test': 15003, 'train': 119982, 'unseen': 4000, 'val': 15004})
- Entrada: 200 x 200, JPEG calidad 90, recorte cuadrado central
- Hiperparámetros: {"pretrained": true, "freeze_backbone": false, "dropout": 0.3, "batch_size": 128, "learning_rate": 0.001, "weight_decay": 0.0001, "epochs": 1, "label_smoothing": 0.0}
- Validación (época 1): ROC-AUC 0.6945, F1 0.6568, accuracy 0.6432
- Test: sin evaluar (correr src.training.evaluate)
- ONNX Runtime en CPU, 1 imagen: p50 2.87 ms (medido en la PC de entrenamiento; en Lambda se mide aparte)
