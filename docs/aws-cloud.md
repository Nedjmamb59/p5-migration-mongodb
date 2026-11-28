# Déployer MongoDB sur AWS — note de recherche

> Étape 3 de la mission : documentation uniquement, aucun déploiement réalisé.
> Recherches effectuées en novembre 2026. Les tarifs AWS évoluent : toujours confirmer avec l'[AWS Pricing Calculator](https://calculator.aws/) avant de chiffrer pour le client.

## Sommaire
1. [Pourquoi passer au cloud ?](#1-pourquoi-passer-au-cloud-)
2. [Créer un compte AWS](#2-créer-un-compte-aws)
3. [Comprendre la tarification AWS](#3-comprendre-la-tarification-aws)
4. [Les options pour héberger MongoDB sur AWS](#4-les-options-pour-héberger-mongodb-sur-aws)
5. [Point d'attention : « RDS pour MongoDB »](#5-point-dattention--rds-pour-mongodb-)
6. [MongoDB conteneurisé sur Amazon ECS](#6-mongodb-conteneurisé-sur-amazon-ecs)
7. [Amazon S3 dans l'architecture](#7-amazon-s3-dans-larchitecture)
8. [Sauvegardes et surveillance](#8-sauvegardes-et-surveillance)
9. [Données de santé : conformité HDS](#9-données-de-santé--conformité-hds)
10. [Recommandation](#10-recommandation)
11. [Sources](#11-sources)

---

## 1. Pourquoi passer au cloud ?

Un **ordinateur** personnel exécute les applications d'un utilisateur ; un **serveur** est une machine dédiée qui fournit un service (ici une base de données) à d'autres machines, en continu, avec redondance matérielle. Le **cloud** consiste à louer ces serveurs (et les services managés construits dessus) à la demande, au lieu de les acheter et de les exploiter soi-même.

Pour notre client, qui rencontre des problèmes de scalabilité :

| Besoin du client | Ce qu'apporte le cloud |
|---|---|
| Absorber la croissance des données | Capacité ajustable en minutes (ajout d'instances, de réplicas, stockage auto-extensible) |
| Ne plus gérer le matériel | Matériel, réseau, électricité, remplacement des disques pris en charge par AWS |
| Haute disponibilité | Réplication sur plusieurs zones de disponibilité (datacenters distincts d'une même région) |
| Maîtriser les coûts | Paiement à l'usage, pas d'investissement initial (CAPEX → OPEX) |
| Sécurité / conformité | Chiffrement au repos et en transit, IAM, journaux d'audit, certifications (dont HDS) |

## 2. Créer un compte AWS

1. Aller sur <https://aws.amazon.com/fr/> → **Créer un compte AWS**.
2. Renseigner une adresse e-mail (qui deviendra l'utilisateur **root**), un nom de compte et vérifier l'e-mail.
3. Choisir le **plan** : depuis le 15 juillet 2025, les nouveaux comptes choisissent entre un *plan gratuit* (jusqu'à 6 mois, sans facturation, accès à une sélection de services) et un *plan payant* (tous les services). Les deux reçoivent 100 $ de crédits à l'inscription, et jusqu'à 100 $ supplémentaires en réalisant des activités de découverte.
4. Saisir les coordonnées et une carte bancaire (vérification d'identité), puis valider le numéro de téléphone.
5. Choisir le plan de support (*Basic*, gratuit, suffit pour démarrer).

**Bonnes pratiques immédiates :**
- activer le **MFA** sur le compte root, puis ne plus l'utiliser au quotidien ;
- créer des utilisateurs nominatifs via **IAM Identity Center**, avec le moindre privilège ;
- créer un **budget AWS** avec alerte e-mail (ex. 20 €/mois) pour éviter les surprises ;
- choisir la région **eu-west-3 (Paris)** pour la localisation des données.

> ⚠️ Pour un service comme DocumentDB ou ECS en production, il faudra le **plan payant** : le plan gratuit ne donne pas accès à tous les services.

## 3. Comprendre la tarification AWS

Principes communs à tous les services :
- **paiement à l'usage** (à la seconde, à l'heure, au Go-mois, au million de requêtes) ;
- **prix différents selon la région** (Paris est en général un peu plus cher que l'Irlande ou la Virginie) ;
- **réductions d'engagement** : instances réservées, *Savings Plans* (1 ou 3 ans) ;
- **capacité Spot** : jusqu'à 70 % moins cher sur Fargate, pour les tâches interruptibles (pas pour une base de données) ;
- le **transfert de données sortant** vers Internet est facturé ; l'entrant est gratuit.

| Service | Ce qui est facturé |
|---|---|
| Amazon DocumentDB | heures d'instance + stockage (Go-mois) + I/O (configuration *Standard*) ou pas d'I/O (configuration *I/O-Optimized*) + sauvegardes au-delà de la franchise |
| Amazon ECS | aucun frais propre à ECS : on paie le calcul sous-jacent (Fargate : vCPU + mémoire à la seconde, minimum 1 minute ; ou instances EC2) |
| Amazon EFS | Go-mois stockés (+ débit selon le mode) |
| Amazon S3 | Go-mois selon la classe de stockage + requêtes + transfert sortant |
| MongoDB Atlas (Marketplace) | consommation Atlas refacturée sur la facture AWS |

Ordres de grandeur relevés (à recalculer pour eu-west-3) :
- DocumentDB : exemple AWS d'un cluster de 2 instances `db.r5.large` à 0,330 €/h l'instance (≈ 482 €/mois pour les deux) et stockage à 0,12 €/Go-mois. Un **essai gratuit d'un mois** existe : 750 h de `db.t3.medium`, 30 millions d'I/O, 5 Go de stockage et 5 Go de sauvegarde.
- S3 Standard : de l'ordre de 0,023 à 0,025 $/Go-mois en Europe ; classes d'archivage (Glacier) environ 6 fois moins chères.
- MongoDB Atlas : niveau gratuit de 512 Mo, clusters dédiés à partir d'environ 0,08 $/h.

**Notre volume** : ~55 000 documents ≈ quelques dizaines de Mo. Le coût sera dominé par le **calcul** (instances), pas par le stockage.

## 4. Les options pour héberger MongoDB sur AWS

| Option | Type | Compatibilité MongoDB | Exploitation | Pour qui ? |
|---|---|---|---|---|
| **Amazon DocumentDB** | Service managé AWS | API MongoDB (versions 5.0 et 8.0 compatibles) — pas le moteur MongoDB lui-même | Très faible (patchs, sauvegardes, bascule automatiques) | Client qui veut du managé 100 % AWS |
| **MongoDB Atlas sur AWS** | Service managé par MongoDB Inc., facturable via AWS Marketplace | Totale (vrai MongoDB) | Très faible | Client qui veut toutes les fonctionnalités MongoDB |
| **MongoDB sur Amazon ECS** (notre conteneur) | Conteneurs managés, base autogérée | Totale | Moyenne : réplication, sauvegardes, mises à jour à notre charge | Réutiliser directement notre docker-compose |
| **MongoDB sur EC2** | Machines virtuelles | Totale | Forte | Besoin de contrôle total |

### Amazon DocumentDB en bref
- Base documentaire **compatible avec l'API MongoDB** : la plupart des pilotes et outils (dont `pymongo`) fonctionnent sans modification.
- **DocumentDB 8.0** (novembre 2025) est compatible avec les pilotes MongoDB 6.0, 7.0 et 8.0 ; la version 8.0.1 (juillet 2026) a ajouté 46 opérateurs d'agrégation.
- Architecture : stockage séparé du calcul, répliqué **6 fois sur 3 zones de disponibilité** ; jusqu'à 15 réplicas en lecture ; ajout d'un réplica en quelques minutes = **scalabilité horizontale des lectures**.
- Deux configurations de stockage : *Standard* (I/O facturées, charges faibles à moyennes) et *I/O-Optimized* (pas de frais d'I/O, intéressant quand les I/O dépassent ~25 % de la facture).
- Version *Elastic Clusters* pour le **sharding** (scalabilité horizontale des écritures).
- TLS obligatoire (1.2 minimum en 8.0), chiffrement au repos via AWS KMS, authentification SCRAM.

**Limite** : ce n'est pas MongoDB. Avant migration, vérifier dans la liste officielle des API supportées les fonctionnalités que notre script utilise (`$jsonSchema`, `Decimal128`, rôles personnalisés, index composés). En cas d'écart, Atlas est l'alternative 100 % compatible.

### Adapter notre script
Seule la chaîne de connexion change (variables d'environnement) : hôte du cluster, `tls=true`, certificat CA d'AWS, `retryWrites=false` pour DocumentDB.

## 5. Point d'attention : « RDS pour MongoDB »

**Amazon RDS ne propose pas MongoDB.** RDS est le service de bases **relationnelles** managées d'AWS : il supporte IBM Db2, MariaDB, Microsoft SQL Server, MySQL, Oracle et PostgreSQL (plus Aurora). Ce que l'on appelle parfois « RDS pour MongoDB » correspond en pratique à **Amazon DocumentDB**, qui reprend la même philosophie que RDS (service managé, sauvegardes automatiques, réplicas, console identique) pour le modèle documentaire.

À présenter au client ainsi : *« L'équivalent RDS pour une base documentaire, c'est DocumentDB. »*

## 6. MongoDB conteneurisé sur Amazon ECS

Amazon ECS orchestre des conteneurs Docker. Notre `docker-compose.yml` se transpose presque directement :

| docker-compose (local) | Équivalent AWS |
|---|---|
| image `mongo:8.0` | même image (ou copie dans **Amazon ECR**, le registre privé AWS) |
| image de migration construite localement | poussée dans **Amazon ECR** |
| service `mongodb` | **Service ECS** (1 tâche permanente) |
| service `migration` | **Tâche ECS ponctuelle** (`run-task`), ou planifiée avec EventBridge |
| volume `mongo_data` | **Amazon EFS** monté sur `/data/db` (persistant au-delà des redémarrages) |
| volume `./data` (CSV) | **Amazon S3** (le script télécharge le CSV au démarrage) |
| réseau `p5_healthcare_net` | **VPC** + sous-réseaux privés + *security groups* (port 27017 ouvert uniquement au service de migration) |
| fichier `.env` | **AWS Secrets Manager** / SSM Parameter Store injectés dans la définition de tâche |
| `docker compose logs` | **CloudWatch Logs** (pilote `awslogs`) |

Étapes :
1. Créer un dépôt ECR et y pousser l'image de migration (`docker build`, `docker tag`, `docker push`).
2. Créer un système de fichiers EFS dans le même VPC (ouvrir le port NFS 2049 aux tâches).
3. Écrire la **définition de tâche** MongoDB : image, CPU/mémoire, variables secrètes, volume EFS monté sur `/data/db`.
4. Créer un **cluster ECS** en mode **Fargate** (pas de serveur à gérer ; EFS supporté depuis la plateforme 1.4.0).
5. Créer le **service** MongoDB (1 tâche désirée, redémarrage automatique en cas d'arrêt).
6. Lancer la **tâche de migration** une fois MongoDB disponible.

**Limites** : une seule tâche MongoDB = pas de haute disponibilité ; la mettre en place (replica set sur 3 tâches) est à notre charge. Les performances d'EFS (stockage réseau NFS) sont inférieures à un disque local pour une base très sollicitée. ECS est donc adapté à un **environnement de recette** ou à une petite production ; pour la production du client, un service managé est préférable.

## 7. Amazon S3 dans l'architecture

S3 est un stockage **objet** (fichiers), pas une base de données. Il intervient à trois niveaux :
- **zone d'atterrissage** des CSV envoyés par le client (versionnage activé, chiffrement SSE-KMS) ;
- **stockage des exports** et des `mongodump` (sauvegardes logiques) ;
- **archivage** à bas coût via des règles de cycle de vie (Standard → Standard-IA → Glacier).

Ses atouts : durabilité conçue pour 99,999999999 % (11 neuf), réplication sur au moins 3 zones de disponibilité pour les classes standard, coût très faible au Go, déclenchement possible d'un traitement à l'arrivée d'un fichier (événement S3 → tâche ECS de migration).

## 8. Sauvegardes et surveillance

### Sauvegardes
| Solution | Fonctionnement |
|---|---|
| DocumentDB (natif) | Sauvegarde continue et incrémentale vers S3, activée par défaut ; restauration à la seconde près (*point-in-time*) sur une fenêtre de rétention réglable de 1 à 35 jours ; snapshots manuels conservés sans limite de durée |
| AWS Backup | Plans de sauvegarde centralisés (DocumentDB, EFS, S3…) : planification, rétention, copies inter-régions ou inter-comptes, coffres immuables |
| MongoDB sur ECS | Sauvegardes AWS Backup du volume EFS + `mongodump` planifié vers S3 |
| Atlas | Sauvegardes continues et restauration à un instant donné intégrées |

Recommandation : rétention de 7 jours minimum en production, un snapshot mensuel conservé 1 an, une copie dans une seconde région. **Tester la restauration** régulièrement.

### Surveillance
- **Amazon CloudWatch** : métriques DocumentDB (CPU, mémoire libre, connexions, latence, stockage des sauvegardes), alarmes par e-mail/SNS ;
- **CloudWatch Logs** : journaux des tâches ECS et journaux d'audit / requêtes lentes (*profiler*) de DocumentDB ;
- **AWS CloudTrail** : traçabilité de toutes les actions d'administration (qui a fait quoi, quand) ;
- **Performance Insights** : analyse des requêtes coûteuses.

Alarmes à créer en priorité : CPU > 80 %, mémoire libre faible, connexions anormales, échec de sauvegarde, budget dépassé.

## 9. Données de santé : conformité HDS

Les données migrées sont des **données de santé à caractère personnel**. En France, leur hébergement impose un hébergeur **certifié HDS** (Hébergeur de Données de Santé), certification délivrée sous l'égide de l'Agence du Numérique en Santé. AWS est certifié HDS, la région **Paris** est couverte depuis mars 2019 ; le périmètre s'étend aujourd'hui à 24 régions.

Conséquences pour le client :
- déployer en **eu-west-3 (Paris)** ;
- signer l'avenant HDS / RGPD avec AWS ;
- vérifier que **chaque service utilisé** est dans le périmètre de la certification ;
- la certification de l'hébergeur ne suffit pas : l'exploitation applicative (comptes, rôles, journalisation) reste sous la responsabilité du client et de DataSoluTech (modèle de **responsabilité partagée**).

## 10. Recommandation

| Critère | DocumentDB | Atlas sur AWS | MongoDB sur ECS |
|---|---|---|---|
| Effort d'exploitation | ★★★ faible | ★★★ faible | ★ élevé |
| Compatibilité avec notre code | ★★ (à valider) | ★★★ totale | ★★★ totale |
| Scalabilité horizontale | ★★★ réplicas / Elastic Clusters | ★★★ sharding natif | ★ manuelle |
| Intégration AWS (IAM, Backup, CloudWatch) | ★★★ native | ★★ | ★★ |
| Coût pour un petit volume | ★★ | ★★★ (petits clusters) | ★★★ |

**Proposition au client** :
1. **Recette** : notre stack Docker sur **ECS Fargate** (réutilisation directe du travail réalisé, coût minimal) ;
2. **Production** : **Amazon DocumentDB** en région Paris (HDS), après validation de compatibilité de nos requêtes — ou **MongoDB Atlas** si une fonctionnalité MongoDB indispensable n'est pas supportée ;
3. **Dans tous les cas** : CSV et exports sur **S3**, secrets dans **Secrets Manager**, sauvegardes via **AWS Backup**, surveillance **CloudWatch**.

## 11. Sources
- AWS — Tarifs Amazon DocumentDB : <https://aws.amazon.com/documentdb/pricing/>
- AWS — Compatibilité DocumentDB / MongoDB : <https://docs.aws.amazon.com/documentdb/latest/developerguide/compatibility.html>
- AWS — Annonce DocumentDB 8.0 (nov. 2025) : <https://aws.amazon.com/about-aws/whats-new/2025/11/documentdb-8-o>
- AWS — DocumentDB 8.0.1, 46 nouveaux opérateurs (juil. 2026) : <https://aws.amazon.com/about-aws/whats-new/2026/07/amazon-documentdb-mongodb-8-0-1-mongo-api>
- AWS — Configurations de stockage DocumentDB : <https://docs.aws.amazon.com/documentdb/latest/developerguide/db-cluster-storage-configs.html>
- AWS — Sauvegarde et restauration DocumentDB : <https://docs.aws.amazon.com/documentdb/latest/developerguide/backup-restore.html>
- AWS — Surveillance DocumentDB avec CloudWatch : <https://docs.aws.amazon.com/documentdb/latest/devguide/cloud_watch.html>
- AWS — Qu'est-ce qu'Amazon RDS (moteurs supportés) : <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Welcome.html>
- AWS — Offre gratuite (nouveau modèle depuis juillet 2025) : <https://aws.amazon.com/free/> et <https://aws.amazon.com/about-aws/whats-new/2025/07/aws-free-tier-credits-month-free-plan>
- AWS — Tarifs Amazon ECS et AWS Fargate : <https://aws.amazon.com/ecs/pricing/>, <https://aws.amazon.com/fargate/pricing/>
- AWS — Volumes EFS pour ECS : <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/tutorial-efs-volumes.html>
- AWS — Tarifs Amazon S3 : <https://aws.amazon.com/s3/pricing/>
- AWS — AWS Backup et DocumentDB : <https://aws.amazon.com/about-aws/whats-new/2021/11/aws-backup-amazon-documentdb-mongodb-compatibility>
- AWS — Certification HDS : <https://aws.amazon.com/fr/compliance/hds/>
- MongoDB Atlas sur AWS Marketplace : <https://aws.amazon.com/marketplace/pp/prodview-pp445qepfdy34>
- AWS — Qu'est-ce que le stockage dans le cloud ? : <https://aws.amazon.com/fr/what-is/cloud-storage/>
