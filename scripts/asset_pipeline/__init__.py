"""
asset_pipeline — общая библиотека для upload_asset.py, watch_assets.py, new_project.py.

Главный принцип всей системы: PROJECT_ID определяет всё. Никакой глобальной
нумерации на весь репозиторий — video_002/shot_001 и video_003/shot_001
это два независимых файла в независимых поддеревьях projects/<id>/.
"""
