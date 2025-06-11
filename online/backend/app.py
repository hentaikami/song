from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import os
import uuid
import base64
import lunardate
import datetime

# 创建 Flask 应用实例
app = Flask(__name__, static_folder='../frontend')

# 配置数据库连接
# 优先使用环境变量中的 DATABASE_URL，若未设置则使用 SQLite 数据库
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///official_positions.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化 SQLAlchemy 数据库对象
db = SQLAlchemy(app)

# 官职模型
class Position(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    dynasty = db.Column(db.String(50))
    category = db.Column(db.String(50))
    description = db.Column(db.Text)
    start_year = db.Column(db.Integer)
    end_year = db.Column(db.Integer)
    rank = db.Column(db.String(50))
    superior_id = db.Column(db.String(36), db.ForeignKey('position.id'))
    subordinates = db.relationship('Position', backref=db.backref('superior', remote_side=[id]))
    image = db.Column(db.Text)  # 存储图片的 Base64 编码

# 关系模型
class Relationship(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id = db.Column(db.String(36), db.ForeignKey('position.id'))
    target_id = db.Column(db.String(36), db.ForeignKey('position.id'))
    relationship_type = db.Column(db.String(50))
    description = db.Column(db.Text)
    source = db.relationship('Position', foreign_keys=[source_id])
    target = db.relationship('Position', foreign_keys=[target_id])

# API 路由

# 获取所有官职信息
@app.route('/api/positions', methods=['GET'])
def get_positions():
    positions = Position.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'dynasty': p.dynasty,
        'category': p.category,
        'description': p.description,
        'start_year': p.start_year,
        'end_year': p.end_year,
        'rank': p.rank,
        'superior_id': p.superior_id,
        'image': p.image
    } for p in positions])

# 添加新的官职信息
@app.route('/api/positions', methods=['POST'])
def add_position():
    data = request.json or {}
    position = Position()
    position.id = data.get('id', str(uuid.uuid4()))
    position.name = data.get('name')
    position.dynasty = data.get('dynasty')
    position.category = data.get('category')
    position.description = data.get('description')
    position.start_year = data.get('start_year')
    position.end_year = data.get('end_year')
    position.rank = data.get('rank')
    position.superior_id = data.get('superior_id')
    position.image = data.get('image')
    db.session.add(position)
    db.session.commit()
    return jsonify({
        'id': position.id,
        'name': position.name
    })

# 更新指定官职信息
@app.route('/api/positions/<id>', methods=['PUT'])
def update_position(id):
    position = Position.query.get_or_404(id)
    data = request.json or {}
    position.name = data.get('name', position.name)
    position.dynasty = data.get('dynasty', position.dynasty)
    position.category = data.get('category', position.category)
    position.description = data.get('description', position.description)
    position.start_year = data.get('start_year', position.start_year)
    position.end_year = data.get('end_year', position.end_year)
    position.rank = data.get('rank', position.rank)
    position.superior_id = data.get('superior_id', position.superior_id)
    position.image = data.get('image', position.image)
    db.session.commit()
    return jsonify({'status': 'success'})

# 删除指定官职信息
@app.route('/api/positions/<id>', methods=['DELETE'])
def delete_position(id):
    position = Position.query.get_or_404(id)
    # 删除相关关系
    Relationship.query.filter_by(source_id=id).delete()
    Relationship.query.filter_by(target_id=id).delete()
    db.session.delete(position)
    db.session.commit()
    return jsonify({'status': 'success'})

# 获取所有关系信息
@app.route('/api/relationships', methods=['GET'])
def get_relationships():
    relationships = Relationship.query.all()
    return jsonify([{
        'id': r.id,
        'source_id': r.source_id,
        'target_id': r.target_id,
        'relationship_type': r.relationship_type,
        'description': r.description
    } for r in relationships])

# 添加新的关系信息
@app.route('/api/relationships', methods=['POST'])
def add_relationship():
    data = request.json or {}
    relationship = Relationship()
    relationship.id = data.get('id', str(uuid.uuid4()))
    relationship.source_id = data.get('source_id')
    relationship.target_id = data.get('target_id')
    relationship.relationship_type = data.get('relationship_type', 'superior')
    relationship.description = data.get('description')
    db.session.add(relationship)
    db.session.commit()
    return jsonify({
        'id': relationship.id,
        'source_id': relationship.source_id,
        'target_id': relationship.target_id
    })

# 删除指定关系信息
@app.route('/api/relationships/<id>', methods=['DELETE'])
def delete_relationship(id):
    relationship = Relationship.query.get_or_404(id)
    db.session.delete(relationship)
    db.session.commit()
    return jsonify({'status': 'success'})

# 农历转换 API
@app.route('/api/lunar', methods=['GET'])
def get_lunar_date():
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    day = request.args.get('day', type=int)
    
    if not all([year, month, day]):
        return jsonify({'error': 'Missing date parameters'}), 400
    
    try:
        # 确保传入的参数为有效的整数
        if year is None or month is None or day is None:
            raise ValueError("Invalid date parameters")
        solar_date = datetime.date(year, month, day)
        lunar = lunardate.LunarDate.fromSolarDate(year, month, day)
        # 假设 lunardate 库有对应的方法，这里简单返回空字符串
        ganzhi_year = getattr(lunar, 'ganzhiYear', lambda: "")()
        ganzhi_month = getattr(lunar, 'ganzhiMonth', lambda: "")()
        ganzhi_day = getattr(lunar, 'ganzhiDay', lambda: "")()
        return jsonify({
            'solar': f"{year}-{month}-{day}",
            'lunar': f"{lunar.year}年{lunar.month}月{lunar.day}日",
            'ganzhi_year': ganzhi_year,
            'ganzhi_month': ganzhi_month,
            'ganzhi_day': ganzhi_day
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# 前端路由
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    static_folder = app.static_folder
    if static_folder and path != "" and os.path.exists(os.path.join(static_folder, path)):
        return send_from_directory(static_folder, path)
    elif static_folder:
        return send_from_directory(static_folder, 'index.html')
    return jsonify({'error': 'Static folder not found'}), 500

if __name__ == '__main__':
    # 在 Render 上运行时，使用环境变量指定的端口
    port = int(os.environ.get('PORT', 5000))
    # 确保使用 0.0.0.0 作为主机地址，以便 Render 可以访问应用
    app.run(host='0.0.0.0', port=port)