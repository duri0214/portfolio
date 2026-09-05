from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from shopping.models import Product, Store, UserAttribute


SHOPPING_SEED_STORES = ["笹塚", "新宿"]

SHOPPING_SEED_USERS = [
    {
        "username": "ピザ焼き太郎",
        "email": "pizza.taro@example.com",
        "first_name": "太郎",
        "last_name": "ピザ焼き",
        "role": UserAttribute.Role.STAFF,
        "nickname": "ピザ焼き太郎",
        "description": "ショッピングアプリの店舗運営を担当しています。",
        "store_name": "笹塚",
        "address": "東京都渋谷区",
        "image": "shopping/profile/pose_dance_ukareru_man.png",
    },
    {
        "username": "買い物するマン",
        "email": "shopping.man@example.com",
        "first_name": "マン",
        "last_name": "買い物する",
        "role": UserAttribute.Role.CUSTOMER,
        "nickname": "買い物するマン",
        "description": "ピザが大好きな常連客です。",
        "address": "神奈川県横浜市",
        "image": None,
    },
]

SHOPPING_SEED_PRODUCTS = [
    {
        "code": "margherita",
        "name": "マルゲリータ",
        "price": 2140,
        "description": "フレッシュトマトとモッツァレラチーズの定番ピザです。",
        "picture": "shopping/products/margherita.jpg",
    },
    {
        "code": "asparagus",
        "name": "モッツァレラとアスパラベーコンのピザ",
        "price": 2680,
        "description": "アスパラの食感とモッツァレラの味わいを楽しめます。",
        "picture": "shopping/products/asparagus.jpg",
    },
    {
        "code": "juicysteak",
        "name": "ジューシーステーキ",
        "price": 2980,
        "description": "特製ビーフステーキの旨味を楽しめるピザです。",
        "picture": "shopping/products/juicysteak.jpg",
    },
]


class Command(BaseCommand):
    help = "Shopping画面の目検用データを作成します"

    @transaction.atomic
    def handle(self, *args, **options):
        stores = {}
        stores_created = 0
        for store_name in SHOPPING_SEED_STORES:
            store, created = Store.objects.get_or_create(name=store_name)
            stores[store_name] = store
            stores_created += int(created)

        user_model = get_user_model()
        users_created = 0
        profiles_created = 0
        for seed_user in SHOPPING_SEED_USERS:
            user_defaults = {
                "email": seed_user["email"],
                "first_name": seed_user["first_name"],
                "last_name": seed_user["last_name"],
            }
            user, created = user_model.objects.get_or_create(
                username=seed_user["username"],
                defaults=user_defaults,
            )
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])
                users_created += 1
            else:
                changed_fields = [
                    field
                    for field, value in user_defaults.items()
                    if getattr(user, field) != value
                ]
                if changed_fields:
                    for field in changed_fields:
                        setattr(user, field, user_defaults[field])
                    user.save(update_fields=changed_fields)

            profile_defaults = {
                "role": seed_user["role"],
                "nickname": seed_user["nickname"],
                "description": seed_user["description"],
                "store": stores.get(seed_user.get("store_name")),
                "address": seed_user["address"],
                "image": seed_user["image"],
            }
            _, profile_created = UserAttribute.objects.update_or_create(
                user=user,
                defaults=profile_defaults,
            )
            profiles_created += int(profile_created)

        products_created = 0
        products_updated = 0
        for seed_product in SHOPPING_SEED_PRODUCTS:
            product, created = Product.objects.get_or_create(
                code=seed_product["code"],
                defaults=seed_product,
            )
            if created:
                products_created += 1
                continue

            changed_fields = []
            for field, value in seed_product.items():
                current_value = (
                    product.picture.name
                    if field == "picture"
                    else getattr(product, field)
                )
                if current_value != value:
                    changed_fields.append(field)
            if changed_fields:
                for field in changed_fields:
                    setattr(product, field, seed_product[field])
                product.save(update_fields=changed_fields)
                products_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Shopping seed completed. "
                f"stores_created={stores_created}, "
                f"users_created={users_created}, "
                f"profiles_created={profiles_created}, "
                f"products_created={products_created}, "
                f"products_updated={products_updated}"
            )
        )
