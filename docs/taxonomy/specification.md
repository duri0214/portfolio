## Category
以下の順番で仕分けされる  
See Also: https://online-hoshujuku.info/english-classification#index_id1
- 界(kingdom)
- 門(phylum)
- 綱(classification)
- 科(family)
- 属(genus)
- 種(species)

## Reference
See Also: [日本産ミミズ大図鑑](https://japanese-mimizu.jimdofree.com/%E3%83%9F%E3%83%9F%E3%82%BA%E3%81%AE%E5%88%86%E9%A1%9E/)  
See Also: [海外のニワトリ](https://en.wikipedia.org/w/index.php?title=Category:Chicken_breeds&from=B)

## Tables
実態としてはmodelクラスにもつので、ドメインクラスとしては表現されない  
See Also: https://mermaid.js.org/syntax/entityRelationshipDiagram.html
```mermaid
erDiagram
    kingdom ||--|{ phylum : contains
    phylum ||--|{ classification : contains
    classification ||--|{ family : contains
    family ||--|{ genus : contains
    genus ||--|{ species : contains
    natural_monument ||--o{ breed : contains
    species ||--o{ breed : contains
    breed ||--o{ breed_tags : contains
    tag ||--o{ breed_tags : contains
    kingdom {
        int id PK
        string name
        string name_en
        string remark
    }
    phylum {
        int id PK
        string name
        string name_en
        string remark
        int kingdom FK
    }
    classification {
        int id PK
        string name
        string name_en
        string remark
        int phylum FK
    }
    family {
        int id PK
        string name
        string name_en
        string remark
        int classification FK
    }
    genus {
        int id PK
        string name
        string name_en
        string remark
        int family FK
    }
    species {
        int id PK
        string name
        string name_en
        string remark
        int genus FK
    }
    natural_monument {
        int id PK
        string name
        string remark
    }
    tag {
        int id PK
        string name
        string remark
    }
    breed {
        int id PK
        string name
        string name_kana
        string image
        string remark
        int natural_monument FK
        int species FK
    }
    breed_tags {
        int id PK
        int breed FK
        int tag FK
    }
```
