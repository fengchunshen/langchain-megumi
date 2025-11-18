"""天眼查批量查询服务 - 处理Excel文件上传、批量查询、数据映射和Excel生成."""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import io
import re

import pandas as pd

from app.chains.tianyancha_search_runnable import TianyanchaSearchRunnable
from app.core.config import settings

logger = logging.getLogger(__name__)


class TianyanchaBatchService:
    """天眼查批量查询服务类."""
    
    def __init__(self):
        """初始化天眼查批量查询服务."""
        self.search_runnable = TianyanchaSearchRunnable()
        logger.info("天眼查批量查询服务初始化完成")
    
    def _parse_reg_capital(self, reg_capital_str: Optional[str]) -> Optional[float]:
        """
        解析注册资本字符串为数值.
        
        支持格式：
        - "1000万" -> 10000000.0
        - "500.5万" -> 5005000.0
        - "1000" -> 1000.0
        - "1000元" -> 1000.0
        
        Args:
            reg_capital_str: 注册资本字符串
        
        Returns:
            Optional[float]: 解析后的数值（单位：元），如果解析失败返回None
        """
        if not reg_capital_str:
            return None
        
        try:
            # 移除空格和特殊字符
            text = str(reg_capital_str).strip().replace(",", "").replace("，", "")
            
            # 提取数字部分
            # 匹配数字（可能包含小数点）和单位
            pattern = r'([\d.]+)\s*([万亿万千百十]?[元]?)'
            match = re.search(pattern, text)
            
            if not match:
                # 如果没有匹配到，尝试直接转换为数字
                return float(re.sub(r'[^\d.]', '', text))
            
            number = float(match.group(1))
            unit = match.group(2) if match.group(2) else ""
            
            # 根据单位转换
            if "万亿" in unit or "万亿" in text:
                return number * 1000000000000
            elif "万" in unit or "万" in text:
                return number * 10000
            elif "千" in unit or "千" in text:
                return number * 1000
            elif "百" in unit or "百" in text:
                return number * 100
            elif "十" in unit or "十" in text:
                return number * 10
            else:
                return number
                
        except Exception as e:
            logger.warning(f"解析注册资本失败: {reg_capital_str}, 错误: {e}")
            return None
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        解析日期字符串为标准格式 YYYY-MM-DD.
        
        Args:
            date_str: 日期字符串
        
        Returns:
            Optional[str]: 标准格式日期字符串，如果解析失败返回None
        """
        if not date_str:
            return None
        
        try:
            # 尝试多种日期格式
            date_str = str(date_str).strip()
            
            # 移除时间部分（如果有）
            if " " in date_str:
                date_str = date_str.split(" ")[0]
            
            # 尝试解析常见格式
            formats = [
                "%Y-%m-%d",
                "%Y/%m/%d",
                "%Y.%m.%d",
                "%Y年%m月%d日",
                "%Y-%m-%d %H:%M:%S",
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue
            
            # 如果都失败，尝试提取年份-月份-日期
            match = re.search(r'(\d{4})[-\/年](\d{1,2})[-\/月](\d{1,2})', date_str)
            if match:
                year = match.group(1)
                month = match.group(2).zfill(2)
                day = match.group(3).zfill(2)
                return f"{year}-{month}-{day}"
            
            return None
            
        except Exception as e:
            logger.warning(f"解析日期失败: {date_str}, 错误: {e}")
            return None
    
    def _parse_address(self, address: Optional[str]) -> tuple:
        """
        解析地址字符串，提取省、市、区.
        
        Args:
            address: 地址字符串
        
        Returns:
            tuple: (province, city, district)
        """
        if not address:
            return None, None, None
        
        try:
            address = str(address).strip()
            
            # 中国省份列表
            provinces = [
                "北京", "天津", "上海", "重庆", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
                "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东",
                "广西", "海南", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆"
            ]
            
            # 查找省份
            province = None
            for p in provinces:
                if address.startswith(p):
                    province = p
                    address = address[len(p):]
                    break
            
            # 查找市（通常以"市"结尾，或在省后面）
            city = None
            city_match = re.search(r'([^省自治区]+?[市州])', address)
            if city_match:
                city = city_match.group(1)
                address = address.replace(city, "", 1)
            
            # 查找区/县
            district = None
            district_match = re.search(r'([^市州]+?[区县])', address)
            if district_match:
                district = district_match.group(1)
            
            return province, city, district
            
        except Exception as e:
            logger.warning(f"解析地址失败: {address}, 错误: {e}")
            return None, None, None
    
    def _map_company_to_db_format(
        self,
        company: Dict[str, Any],
        search_word: str
    ) -> Dict[str, Any]:
        """
        将天眼查返回的企业信息映射到数据库表格式.
        
        Args:
            company: 企业信息字典（来自天眼查基础信息API）
            search_word: 搜索关键词
        
        Returns:
            Dict[str, Any]: 映射后的企业数据字典
        """
        # 解析注册资本
        reg_capital_value = self._parse_reg_capital(company.get("regCapital"))
        
        # 解析成立日期（新接口返回时间戳）
        estiblish_time = company.get("estiblishTime")
        if estiblish_time:
            # 如果是时间戳（毫秒），转换为日期字符串
            try:
                from datetime import datetime
                dt = datetime.fromtimestamp(estiblish_time / 1000)
                reg_date = dt.strftime("%Y-%m-%d")
            except:
                reg_date = self._parse_date(estiblish_time)
        else:
            reg_date = None
        
        # 解析地址 - 优先使用新接口提供的 city 和 district 字段
        reg_location = company.get("regLocation") or company.get("base", "")
        city = company.get("city")
        district = company.get("district")
        
        # 如果没有 city 和 district，尝试从地址解析
        if not city or not district:
            province_parsed, city_parsed, district_parsed = self._parse_address(reg_location)
            if not city:
                city = city_parsed
            if not district:
                district = district_parsed
            province = province_parsed
        else:
            # 如果有 city，尝试从 city 解析省份
            province, _, _ = self._parse_address(city)
        
        # 构建数据库记录
        record = {
            "company_name": company.get("name", ""),
            "juridical_person": company.get("legalPersonName", ""),
            "credit_code": company.get("creditCode", ""),
            "reg_capital_type": company.get("regCapitalCurrency"),  # 使用注册资本币种
            "reg_capital": reg_capital_value,
            "reg_date": reg_date,
            "company_type": company.get("companyOrgType"),  # 使用企业类型
            "company_honor": None,  # 天眼查API未提供此字段
            "company_status": company.get("regStatus", ""),
            "address": reg_location,
            "province": province,
            "city": city,
            "district": district,
            "industry": company.get("industry"),  # 新接口提供行业信息
            "employee_size": company.get("staffNumRange"),  # 新接口提供员工规模
            "business_scope": company.get("businessScope"),  # 新接口提供经营范围
            "annual_social_productive_value": None,  # 天眼查API未提供此字段
            "write_off_date": self._parse_date(company.get("cancelDate")),  # 注销日期
            "is_settled": None,  # 需要业务逻辑判断
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "del_flag": "0",
            "status": 1,
            "sort": 0,
            "remark": f"来源：天眼查基础信息，搜索关键词：{search_word}"
        }
        
        return record
    
    def _read_company_names_from_excel(self, file_content: bytes) -> List[str]:
        """
        从Excel文件中读取企业名称列表.
        
        Args:
            file_content: Excel文件内容（字节）
        
        Returns:
            List[str]: 企业名称列表
        
        Raises:
            ValueError: 文件格式错误或无法读取
        """
        try:
            # 读取Excel文件
            df = pd.read_excel(io.BytesIO(file_content), engine='openpyxl')
            
            # 尝试找到包含企业名称的列
            # 常见列名：企业名称、公司名称、名称、name、company_name等
            possible_columns = [
                "企业名称", "公司名称", "名称", "name", "company_name",
                "企业名", "公司名", "单位名称", "机构名称"
            ]
            
            company_column = None
            for col in possible_columns:
                if col in df.columns:
                    company_column = col
                    break
            
            # 如果没找到，使用第一列
            if company_column is None:
                company_column = df.columns[0]
                logger.warning(f"未找到标准的企业名称列，使用第一列: {company_column}")
            
            # 提取企业名称，去除空值和重复
            company_names = df[company_column].dropna().astype(str).str.strip()
            company_names = company_names[company_names != ""].unique().tolist()
            
            logger.info(f"从Excel文件中读取到 {len(company_names)} 个企业名称")
            return company_names
            
        except Exception as e:
            logger.error(f"读取Excel文件失败: {e}")
            raise ValueError(f"无法读取Excel文件: {str(e)}")
    
    async def _search_company(
        self,
        company_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        搜索单个企业，返回企业基础信息.
        
        Args:
            company_name: 企业名称（或公司id、注册号、社会统一信用代码）
        
        Returns:
            Optional[Dict[str, Any]]: 企业信息字典，如果未找到返回None
        """
        try:
            # 直接调用天眼查基础信息API
            import httpx
            from app.core.config import settings
            
            api_url = "http://open.api.tianyancha.com/services/open/ic/baseinfo/normal"
            api_token = settings.TIANYANCHA_API_TOKEN
            
            if not api_token:
                raise ValueError("天眼查API Token未配置")
            
            params = {
                "keyword": company_name
            }
            
            headers = {
                "Authorization": api_token
            }
            
            async with httpx.AsyncClient(timeout=settings.TIMEOUT) as client:
                response = await client.get(
                    api_url,
                    params=params,
                    headers=headers
                )
                
                if response.status_code != 200:
                    logger.warning(f"天眼查API请求失败，状态码: {response.status_code}, 企业: {company_name}")
                    return None
                
                result = response.json()
                
                # 检查API返回的错误码
                error_code = result.get("error_code", 0)
                if error_code != 0:
                    logger.warning(f"天眼查API返回错误: {result.get('reason', '未知错误')}, 企业: {company_name}")
                    return None
                
                # 解析结果 - 新接口直接返回单个企业信息
                result_data = result.get("result", {})
                
                if not result_data:
                    return None
                
                return result_data
                
        except Exception as e:
            logger.error(f"搜索企业失败: {company_name}, 错误: {e}")
            return None
    
    async def batch_query_companies(
        self,
        file_content: bytes,
        max_concurrent: int = 5
    ) -> Tuple[bytes, int, int, int]:
        """
        批量查询企业信息并生成Excel文件.
        
        Args:
            file_content: 上传的Excel文件内容（字节）
            max_concurrent: 最大并发查询数
        
        Returns:
            tuple[bytes, int, int, int]: (Excel文件内容, 总数量, 成功数量, 失败数量)
        
        Raises:
            ValueError: 文件格式错误或无法读取
        """
        # 读取企业名称列表
        company_names = self._read_company_names_from_excel(file_content)
        
        if not company_names:
            raise ValueError("Excel文件中没有找到有效的企业名称")
        
        logger.info(f"开始批量查询 {len(company_names)} 个企业")
        
        # 批量查询企业信息
        results: List[Dict[str, Any]] = []
        success_count = 0
        failed_count = 0
        
        # 使用异步批量查询
        import asyncio
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def search_with_semaphore(company_name: str):
            async with semaphore:
                return await self._search_company(company_name)
        
        tasks = [search_with_semaphore(name) for name in company_names]
        companies = await asyncio.gather(*tasks)
        
        # 处理查询结果
        for idx, (company_name, company) in enumerate(zip(company_names, companies)):
            if company:
                # 映射到数据库格式
                record = self._map_company_to_db_format(company, company_name)
                results.append(record)
                success_count += 1
                logger.info(f"查询成功 [{idx+1}/{len(company_names)}]: {company_name}")
            else:
                # 查询失败，创建空记录
                record = {
                    "company_name": company_name,
                    "juridical_person": None,
                    "credit_code": None,
                    "reg_capital_type": None,
                    "reg_capital": None,
                    "reg_date": None,
                    "company_type": None,
                    "company_honor": None,
                    "company_status": None,
                    "address": None,
                    "province": None,
                    "city": None,
                    "district": None,
                    "industry": None,
                    "employee_size": None,
                    "business_scope": None,
                    "annual_social_productive_value": None,
                    "write_off_date": None,
                    "is_settled": None,
                    "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "del_flag": "0",
                    "status": 1,
                    "sort": 0,
                    "remark": f"查询失败：未找到该企业信息"
                }
                results.append(record)
                failed_count += 1
                logger.warning(f"查询失败 [{idx+1}/{len(company_names)}]: {company_name}")
        
        # 生成Excel文件
        df = pd.DataFrame(results)
        
        # 按照数据库表字段顺序排列列
        column_order = [
            "company_name", "juridical_person", "credit_code", "reg_capital_type",
            "reg_capital", "reg_date", "company_type", "company_honor", "company_status",
            "address", "province", "city", "district", "industry", "employee_size",
            "business_scope", "annual_social_productive_value", "write_off_date",
            "is_settled", "create_time", "update_time", "del_flag", "status", "sort", "remark"
        ]
        
        # 确保所有列都存在
        for col in column_order:
            if col not in df.columns:
                df[col] = None
        
        # 重新排列列顺序
        df = df[column_order]
        
        # 生成Excel文件
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='企业信息')
        
        output.seek(0)
        excel_content = output.read()
        
        total_count = len(company_names)
        logger.info(f"批量查询完成：成功 {success_count} 个，失败 {failed_count} 个")
        
        return excel_content, total_count, success_count, failed_count


# 创建全局服务实例
tianyancha_batch_service = TianyanchaBatchService()

