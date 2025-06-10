# backend/app.py 文件

# 1. 导入CORS模块（在文件顶部添加）
from flask_cors import CORS  # 添加这一行
from flask import Flask, request, jsonify, Response, make_response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import json
from typing import List, Dict, Any, Optional, Union
from lunardate import LunarDate

app = Flask(__name__)
CORS(app, origins=["http://localhost:8000"], supports_credentials=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///official_positions.db'
db = SQLAlchemy(app)

# 数据模型
class Position(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('position.id'))
    children = db.relationship('Position', backref=db.backref('parent', remote_side=[id]))

    def to_dict(self) -> Dict[str, Any]:
        return {'id': self.id, 'name': self.name, 'parent_id': self.parent_id}

class PositionFunction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    position_id = db.Column(db.Integer, db.ForeignKey('position.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text)
    source_text = db.Column(db.Text)
    source_reference = db.Column(db.String(200))

    position = db.relationship('Position', backref='functions')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'date': self.date.isoformat(),
            'description': self.description,
            'source_text': self.source_text,
            'source_reference': self.source_reference
        }

class Official(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    bio = db.Column(db.Text)

    def to_dict(self) -> Dict[str, Any]:
        return {'id': self.id, 'name': self.name, 'bio': self.bio}

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    position_id = db.Column(db.Integer, db.ForeignKey('position.id'), nullable=False)
    official_id = db.Column(db.Integer, db.ForeignKey('official.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    source_text = db.Column(db.Text)
    source_reference = db.Column(db.String(200))

    position = db.relationship('Position', backref='appointments')
    official = db.relationship('Official', backref='appointments')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'position_id': self.position_id,
            'official_id': self.official_id,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'source_text': self.source_text,
            'source_reference': self.source_reference
        }

class Connection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_position_id = db.Column(db.Integer, db.ForeignKey('position.id'), nullable=False)
    to_position_id = db.Column(db.Integer, db.ForeignKey('position.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    label = db.Column(db.String(100))
    color = db.Column(db.String(20))
    style = db.Column(db.String(20))
    is_visible = db.Column(db.Boolean, default=True)
    source_text = db.Column(db.Text)
    source_reference = db.Column(db.String(200))

    from_position = db.relationship('Position', foreign_keys=[from_position_id])
    to_position = db.relationship('Position', foreign_keys=[to_position_id])

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'from_position_id': self.from_position_id,
            'to_position_id': self.to_position_id,
            'date': self.date.isoformat(),
            'label': self.label,
            'color': self.color,
            'style': self.style,
            'is_visible': self.is_visible,
            'source_text': self.source_text,
            'source_reference': self.source_reference
        }

# 日期转换辅助函数
def get_lunar_date(g_date: date) -> str:
    try:
        lunar = LunarDate.fromSolarDate(g_date.year, g_date.month, g_date.day)
        return f"{lunar.year}年{lunar.month}月{lunar.day}日"
    except (ValueError, IndexError) as e:
        print(f"日期转换错误: {e}")
        return "转换失败"

def get_ganzhi_date(g_date: date) -> str:
    base_date = date(1984, 2, 2)  # 甲子年正月初一
    ganzhi_stems = "甲乙丙丁戊己庚辛壬癸"
    ganzhi_branches = "子丑寅卯辰巳午未申酉戌亥"
    delta_days = (g_date - base_date).days
    stem_index = (delta_days % 10 + 10) % 10
    branch_index = (delta_days % 12 + 12) % 12
    return f"{ganzhi_stems[stem_index]}{ganzhi_branches[branch_index]}日"

def parse_date(date_str: Optional[str]) -> date:
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.now().date()
    except ValueError:
        raise ValueError("Invalid date format. Use YYYY-MM-DD")

# API路由
@app.route('/api/positions', methods=['GET', 'POST'])  # 新增POST方法支持
def get_positions() -> Response:
    if request.method == 'GET':
        try:
            target_date = parse_date(request.args.get('date'))
        except ValueError as e:
            return make_response(jsonify({"error": str(e)}), 400)
        
        positions = Position.query.all()
        result = []
        
        for pos in positions:
            # 获取指定日期的职能信息
            func = PositionFunction.query.filter(
                PositionFunction.position_id == pos.id,
                PositionFunction.date <= target_date
            ).order_by(PositionFunction.date.desc()).first()
            
            # 获取指定日期的任职官员
            appointments = Appointment.query.filter(
                Appointment.position_id == pos.id,
                Appointment.start_date <= target_date,
                (Appointment.end_date.is_(None) | (Appointment.end_date >= target_date))
            ).all()
            
            pos_dict = pos.to_dict()
            pos_dict['function'] = func.to_dict() if func else None
            pos_dict['appointments'] = [app.to_dict() for app in appointments]
            
            result.append(pos_dict)
        
        return jsonify(result)
    
    elif request.method == 'POST':
        # 处理创建新职位的逻辑
        data = request.get_json()  # 修改：使用 get_json() 确保正确解析 JSON 数据
        print(f"Received POST data: {data}")  # 添加日志输出
        
        # 验证职位名称是否为空
        name = data.get('name') if data else None
        if not name or name.strip() == '':
            print("职位名称为空")  # 添加日志输出
            return make_response(jsonify({"error": "职位名称不能为空"}), 400)
        
        # 创建新职位
        new_position = Position()
        new_position.name = name
        new_position.parent_id = data.get('parent_id')  # 修正：使用parent_id而非category
        db.session.add(new_position)
        db.session.commit()
        
        # 如果有职能信息，创建对应的职能记录
        if data and 'function' in data:
            func_data = data['function']
            try:
                date_str = func_data.get('date') or data.get('date')
                date = parse_date(date_str)
            except ValueError as e:
                print(f"日期解析错误: {e}")  # 添加日志输出
                return make_response(jsonify({"error": str(e)}), 400)
            
            new_func = PositionFunction()
            new_func.position_id = new_position.id
            new_func.date = date
            new_func.description = func_data.get('description')
            new_func.source_text = func_data.get('source_text')
            new_func.source_reference = func_data.get('source_reference')
            db.session.add(new_func)
            db.session.commit()
        
        return jsonify({
            'success': True,
            'id': new_position.id,
            'message': '职位创建成功'
        })
    # 添加默认返回值
    return make_response(jsonify({"error": "Invalid request method"}), 405)

@app.route('/api/positions/<int:position_id>', methods=['GET', 'PUT'])  # 移除POST，仅保留GET和PUT
def position_detail(position_id: int) -> Response:
    position = Position.query.get_or_404(position_id)
    
    if request.method == 'GET':
        try:
            target_date = parse_date(request.args.get('date'))
        except ValueError as e:
            return make_response(jsonify({"error": str(e)}), 400)
        
        # 获取职能历史
        functions = PositionFunction.query.filter(
            PositionFunction.position_id == position_id
        ).order_by(PositionFunction.date).all()
        
        # 获取任职历史
        appointments = Appointment.query.filter(
            Appointment.position_id == position_id
        ).order_by(Appointment.start_date).all()
        
        return jsonify({
            'position': position.to_dict(),
            'functions': [f.to_dict() for f in functions],
            'appointments': [a.to_dict() for a in appointments]
        })
    
    elif request.method == 'PUT':
        data = request.json or {}
        try:
            target_date = parse_date(data.get('date'))
        except ValueError as e:
            return make_response(jsonify({"error": str(e)}), 400)
        
        # 更新职位基本信息
        position.name = data.get('name', position.name)
        position.parent_id = data.get('parent_id', position.parent_id)  # 修正：使用parent_id而非category
        
        # 更新或创建职能信息
        if 'function' in data:
            func_data = data['function']
            existing_func = PositionFunction.query.filter(
                PositionFunction.position_id == position_id,
                PositionFunction.date == target_date
            ).first()
            
            if existing_func:
                existing_func.description = func_data.get('description', existing_func.description)
                existing_func.source_text = func_data.get('source_text', existing_func.source_text)
                existing_func.source_reference = func_data.get('source_reference', existing_func.source_reference)
            else:
                new_func = PositionFunction()
                new_func.position_id = position_id
                new_func.date = target_date
                new_func.description = func_data.get('description')
                new_func.source_text = func_data.get('source_text')
                new_func.source_reference = func_data.get('source_reference')
                db.session.add(new_func)
        
        # 更新或创建任职信息
        if 'appointments' in data:
            for app_data in data['appointments']:
                if 'id' in app_data:
                    appointment = Appointment.query.get(app_data['id'])
                    if appointment:
                        appointment.official_id = app_data.get('official_id', appointment.official_id)
                        appointment.start_date = app_data.get('start_date', appointment.start_date)
                        appointment.end_date = app_data.get('end_date', appointment.end_date)
                        appointment.source_text = app_data.get('source_text', appointment.source_text)
                        appointment.source_reference = app_data.get('source_reference', appointment.source_reference)
                else:
                    new_app = Appointment()
                    new_app.position_id = position_id
                    new_app.official_id = app_data['official_id']
                    new_app.start_date = app_data['start_date']
                    new_app.end_date = app_data.get('end_date')
                    new_app.source_text = app_data.get('source_text')
                    new_app.source_reference = app_data.get('source_reference')
                    db.session.add(new_app)
        
        db.session.commit()
        return jsonify({'success': True, 'message': '职位更新成功'})
    # 添加默认返回值
    return make_response(jsonify({"error": "Invalid request method"}), 405)

@app.route('/api/officials/<int:official_id>', methods=['GET', 'PUT'])  # 修改：将POST改为PUT
def official_detail(official_id: int) -> Response:
    if request.method == 'GET':
        official = Official.query.get_or_404(official_id)
        appointments = Appointment.query.filter(
            Appointment.official_id == official_id
        ).order_by(Appointment.start_date).all()
        
        return jsonify({
            'official': official.to_dict(),
            'appointments': [a.to_dict() for a in appointments]
        })
    
    elif request.method == 'PUT':  # 修改：将POST改为PUT
        data = request.json or {}
        official = Official.query.get_or_404(official_id)
        
        official.name = data.get('name', official.name)
        official.bio = data.get('bio', official.bio)
        
        db.session.commit()
        return jsonify({'success': True, 'id': official.id})
    # 添加默认返回值
    return make_response(jsonify({"error": "Invalid request method"}), 405)

@app.route('/api/connections', methods=['GET', 'POST'])
def connections() -> Response:
    if request.method == 'GET':
        try:
            target_date = parse_date(request.args.get('date'))
        except ValueError as e:
            return make_response(jsonify({"error": str(e)}), 400)
        
        connections = Connection.query.filter(
            Connection.date <= target_date
        ).all()
        
        return jsonify([conn.to_dict() for conn in connections])
    
    elif request.method == 'POST':
        data = request.json or {}
        new_conn = Connection()
        new_conn.from_position_id = data.get('from_position_id')
        new_conn.to_position_id = data.get('to_position_id')
        try:
            date_str = data.get('date')
            if date_str:
                new_conn.date = parse_date(date_str)
        except ValueError as e:
            return make_response(jsonify({"error": str(e)}), 400)
        new_conn.label = data.get('label')
        new_conn.color = data.get('color', '#000000')
        new_conn.style = data.get('style', 'solid')
        new_conn.is_visible = data.get('is_visible', True)
        new_conn.source_text = data.get('source_text')
        new_conn.source_reference = data.get('source_reference')
        db.session.add(new_conn)
        db.session.commit()
        return jsonify({'success': True, 'id': new_conn.id})
    # 添加默认返回值
    return make_response(jsonify({"error": "Invalid request method"}), 405)

@app.route('/api/date-convert', methods=['GET'])
def date_convert() -> Response:
    date_str = request.args.get('date')
    try:
        date_obj = parse_date(date_str)
    except ValueError as e:
        return make_response(jsonify({"error": str(e)}), 400)
    
    lunar_date = get_lunar_date(date_obj)
    ganzhi_date = get_ganzhi_date(date_obj)
    return jsonify({
        'gregorian': date_obj.strftime('%Y-%m-%d'),
        'lunar': lunar_date,
        'ganzhi': ganzhi_date
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)