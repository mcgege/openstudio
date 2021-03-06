import React from "react"
import { v4 } from "uuid"

import Label from '../../../components/ui/Label'

const bookingStatusLabelClass = (status) => {
    switch (status) {
        case "attending":
            return "label-success"
        case "booked":
            return "label-primary"
        case "cancelled":
            return "label-warning"
    }
}

const bookingStatusMessage = (status, intl) => {
    switch (status) {
        case "attending":
            return intl.formatMessage({ id: 'app.pos.checkin.attendance.status.attending' })
        case "booked":
            return intl.formatMessage({ id: 'app.pos.checkin.attendance.status.booked' })
        case "cancelled":
            return intl.formatMessage({ id: 'app.pos.checkin.attendance.status.cancelled' })
    }
}


const ManageBooking = ({clattID, status, onClick=f=>f, onClickRemove=f=>f, collapseID}) =>
    <div className="pull-right">
        <button className="btn btn-default" type="button" data-toggle="collapse" data-target={`#${collapseID}`} aria-expanded="false" aria-controls="collapseExample">
            Manage booking
        </button>
        <div className="collapse" id={collapseID}>
            <br />
            <div className="well">
                {(status == "booked") ? "" :
                <button className="btn btn-primary"
                        onClick={() => onClick(clattID, "booked")}>
                    Booked
                </button> }
                {(status == "cancelled") ? "" :
                <button className="btn btn-warning"
                        onClick={() => onClick(clattID, "cancelled")}>
                    Cancelled
                </button>}
                <button className="btn btn-danger"
                        onClick={()=> onClickRemove(clattID)}>
                    Remove
                </button>
            </div>
        </div>
    </div>


const ButtonCheckin = ({clattID, onClick=f=>f}) =>
    <button className='btn btn-default pull-right' onClick={() => onClick(clattID, "attending")}>
        Check-in
    </button>


const CustomerCheckIn = ({clattID, status, onClick=f=>f, onClickRemove=f=>f}) => {
    console.log(status)
    switch (status) {
        case "booked":
            return <ButtonCheckin onClick={onClick}
                                  clattID={clattID} />
        default:
            // "cancelled" and "checked-in"
            return <ManageBooking clattID={clattID}
                                  status={status}
                                  onClick={onClick}
                                  onClickRemove={onClickRemove}
                                  collapseID={v4()} />
    }
}


const AttendanceList = ({attendance_items, intl, title="", onClick=f=>f, onClickRemove=f=>f}) => 
    <div className="box box-default"> 
        <div className="box-header">
            <h3 className="box-title">{title}</h3>
        </div>
        <div className="box-body">
            <table className="table table-striped table-hover">
                    <thead>
                        <tr>
                            <th></th>
                            <th>Customer</th>
                            <th>Check-in status</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        {attendance_items.map((item, i) => 
                            <tr key={v4()} >
                                {console.log(item)}
                                {console.log(item.auth_user.thumbsmall)}
                                <td className="customers_list_image"><img src={item.auth_user.thumbsmall}></img></td>
                                <td>{item.auth_user.display_name}</td>
                                <td><Label type={bookingStatusLabelClass(item.classes_attendance.BookingStatus)}>
                                        {bookingStatusMessage(item.classes_attendance.BookingStatus, intl)}
                                    </Label> 
                                    {' '}
                                    {(item.classes_reservation.id) ? 
                                        <Label type="label-default">
                                            {intl.formatMessage({ id: 'app.pos.checkin.attendance.label_enrolled' })}
                                        </Label> : ''}
                                    <br />
                                    <span className="text-muted"><small>{(item.classes_attendance.CreatedOn)}</small></span>
                                </td>
                                <td><CustomerCheckIn clattID={item.classes_attendance.id}
                                                     status={item.classes_attendance.BookingStatus}
                                                     onClick={onClick}
                                                     onClickRemove={onClickRemove} /></td>
                            </tr>
                        )}
                    </tbody>
                </table>
            {/* {attendance_items.map((ai, i) => 
                <AttendanceListItem key={"ai_" + v4()}
                                    data={ai} />
            )} */}
        </div>
    </div>


export default AttendanceList